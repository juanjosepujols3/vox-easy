use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, LogicalPosition,
};

mod audio;

#[tauri::command]
fn start_recording() -> Result<(), String> {
    audio::start_recording().map_err(|e| e.to_string())
}

#[tauri::command]
fn stop_recording() -> Result<Vec<u8>, String> {
    audio::stop_recording().map_err(|e| e.to_string())
}

#[tauri::command]
fn is_recording() -> bool {
    audio::is_recording()
}

#[tauri::command]
async fn show_recording_popup(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("recording") {
        // Position popup at bottom center of screen
        if let Ok(monitor) = window.current_monitor() {
            if let Some(monitor) = monitor {
                let size = monitor.size();
                let scale = monitor.scale_factor();
                let x = (size.width as f64 / scale / 2.0) - 80.0; // Center horizontally
                let y = (size.height as f64 / scale) - 150.0; // Near bottom
                log::info!("Positioning popup at x={}, y={}", x, y);
                let _ = window.set_position(LogicalPosition::new(x, y));
            }
        }
        window.show().map_err(|e| e.to_string())?;
        // Don't steal focus from the active app
    }
    Ok(())
}

#[tauri::command]
async fn hide_recording_popup(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("recording") {
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn paste_text() -> Result<(), String> {
    // Use AppleScript to simulate Cmd+V paste
    // Small delay to ensure clipboard is ready
    std::thread::sleep(std::time::Duration::from_millis(100));

    let output = std::process::Command::new("osascript")
        .args([
            "-e",
            r#"tell application "System Events" to keystroke "v" using command down"#,
        ])
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        let error = String::from_utf8_lossy(&output.stderr);
        log::error!("Failed to paste: {}", error);
        return Err(format!("Failed to paste: {}", error));
    }

    log::info!("Text pasted successfully");
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .setup(|app| {
            // Setup logging in debug mode
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Create system tray
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Dictado - Speech to Text")
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_recording,
            stop_recording,
            is_recording,
            show_recording_popup,
            hide_recording_popup,
            paste_text
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
