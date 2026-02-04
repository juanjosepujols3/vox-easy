export type Page = 'dashboard' | 'settings' | 'license'

export interface Hotkey {
  cmd: boolean
  ctrl: boolean
  shift: boolean
  alt: boolean
  key: string
}
