const express = require('express');
const cors = require('cors');
const multer = require('multer');
const FormData = require('form-data');
const fetch = require('node-fetch');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

// Enable CORS for all origins (the desktop and web apps)
app.use(cors());
app.use(express.json());

// Simple file-based storage (use a real database in production)
const DATA_FILE = path.join(__dirname, 'data.json');

// Your Groq API key (set as environment variable in production)
const GROQ_API_KEY = process.env.GROQ_API_KEY || 'YOUR_GROQ_API_KEY_HERE';

// Free tier limits
const FREE_MINUTES_PER_DAY = 5;

// Load data
function loadData() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    }
  } catch (e) {
    console.error('Error loading data:', e);
  }
  return { users: {}, licenses: {} };
}

// Save data
function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// Get or create user
function getUser(deviceId) {
  const data = loadData();
  if (!data.users[deviceId]) {
    data.users[deviceId] = {
      deviceId,
      createdAt: new Date().toISOString(),
      isPro: false,
      licenseKey: null,
      usage: {}
    };
    saveData(data);
  }
  return data.users[deviceId];
}

// Get today's date string
function getToday() {
  return new Date().toISOString().split('T')[0];
}

// Check if user can transcribe
function canTranscribe(deviceId) {
  const user = getUser(deviceId);
  const today = getToday();

  // Pro users have unlimited access
  if (user.isPro) {
    return { allowed: true, remaining: Infinity, isPro: true };
  }

  // Check daily usage
  const todayUsage = user.usage[today] || 0;
  const remaining = Math.max(0, FREE_MINUTES_PER_DAY - todayUsage);

  return {
    allowed: remaining > 0,
    remaining,
    isPro: false,
    used: todayUsage,
    limit: FREE_MINUTES_PER_DAY
  };
}

// Add usage minutes
function addUsage(deviceId, minutes) {
  const data = loadData();
  const user = data.users[deviceId];
  if (user) {
    const today = getToday();
    user.usage[today] = (user.usage[today] || 0) + minutes;
    saveData(data);
  }
}

// Activate Pro license
function activateLicense(deviceId, licenseKey) {
  const data = loadData();

  // Check if license is valid (simple check - in production use a proper system)
  // License format: DICTADO-XXXX-XXXX-XXXX
  if (!licenseKey.startsWith('DICTADO-') || licenseKey.length !== 23) {
    return { success: false, error: 'Licencia inválida' };
  }

  // Check if license is already used
  if (data.licenses[licenseKey] && data.licenses[licenseKey] !== deviceId) {
    return { success: false, error: 'Esta licencia ya está en uso' };
  }

  // Activate license
  data.licenses[licenseKey] = deviceId;
  if (data.users[deviceId]) {
    data.users[deviceId].isPro = true;
    data.users[deviceId].licenseKey = licenseKey;
  }
  saveData(data);

  return { success: true };
}

// Health check
app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    service: 'Dictado API',
    version: '1.0.0'
  });
});

// Check usage status
app.get('/api/status', (req, res) => {
  const deviceId = req.headers['x-device-id'];
  if (!deviceId) {
    return res.status(400).json({ error: 'Device ID required' });
  }

  const status = canTranscribe(deviceId);
  res.json(status);
});

// Transcribe audio
app.post('/api/transcribe', upload.single('audio'), async (req, res) => {
  const deviceId = req.headers['x-device-id'];

  if (!deviceId) {
    return res.status(400).json({ error: 'Device ID required' });
  }

  if (!req.file) {
    return res.status(400).json({ error: 'Audio file required' });
  }

  // Check if user can transcribe
  const status = canTranscribe(deviceId);
  if (!status.allowed) {
    return res.status(403).json({
      error: 'Límite diario alcanzado',
      message: 'Has alcanzado el límite de 5 minutos diarios. Actualiza a Pro para uso ilimitado.',
      ...status
    });
  }

  try {
    // Forward to Groq API
    const formData = new FormData();
    formData.append('file', req.file.buffer, {
      filename: 'audio.wav',
      contentType: 'audio/wav'
    });
    formData.append('model', 'whisper-large-v3');

    const language = req.body.language;
    if (language) {
      formData.append('language', language);
    }

    const response = await fetch('https://api.groq.com/openai/v1/audio/transcriptions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${GROQ_API_KEY}`,
        ...formData.getHeaders()
      },
      body: formData
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      console.error('Groq API error:', error);
      return res.status(response.status).json({
        error: error.error?.message || 'Error en la transcripción'
      });
    }

    const result = await response.json();

    // Estimate duration (rough: 150 words per minute average)
    const wordCount = result.text.split(/\s+/).length;
    const estimatedMinutes = Math.max(0.1, wordCount / 150);

    // Add usage
    addUsage(deviceId, estimatedMinutes);

    // Get updated status
    const newStatus = canTranscribe(deviceId);

    res.json({
      text: result.text,
      duration: estimatedMinutes,
      status: newStatus
    });

  } catch (error) {
    console.error('Transcription error:', error);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

// Activate Pro license
app.post('/api/activate', (req, res) => {
  const deviceId = req.headers['x-device-id'];
  const { licenseKey } = req.body;

  if (!deviceId) {
    return res.status(400).json({ error: 'Device ID required' });
  }

  if (!licenseKey) {
    return res.status(400).json({ error: 'License key required' });
  }

  const result = activateLicense(deviceId, licenseKey);

  if (result.success) {
    res.json({ success: true, message: '¡Licencia Pro activada!' });
  } else {
    res.status(400).json({ success: false, error: result.error });
  }
});

// Generate license (admin endpoint - protect in production!)
app.post('/api/admin/generate-license', (req, res) => {
  const adminKey = req.headers['x-admin-key'];

  // Simple admin auth (use proper auth in production)
  if (adminKey !== process.env.ADMIN_KEY && adminKey !== 'dictado-admin-2024') {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Generate license key
  const segments = [
    'DICTADO',
    uuidv4().substring(0, 4).toUpperCase(),
    uuidv4().substring(0, 4).toUpperCase(),
    uuidv4().substring(0, 4).toUpperCase()
  ];
  const licenseKey = segments.join('-');

  res.json({ licenseKey });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`🎤 Dictado API running on port ${PORT}`);
  console.log(`   Health check: http://localhost:${PORT}/`);
});
