const app = require('./app');
const http = require('http');
const PORT = process.env.PORT || 3000;
const path = require('path');
const cors = require('cors');
const rateLimit = require('express-rate-limit');

const rootDir = require('./utils/pathUtils');
const redactionRouter = require('./routes/redactRouter');
const peekRouter = require('./routes/peekRouter');
const compressRouter = require('./routes/compressRouter');
const compressPPTRouter = require('./routes/compressPPTRouter');
const splitRouter = require('./routes/splitRouter');
const encryptRouter = require('./routes/encryptionRouter');
const repairRouter = require('./routes/repairPDFRouter');
const convertRouter = require('./routes/convertRouter');

const { mongoConnect } = require('./utils/database');
const isAuthenticated = require('./middlewares/auth.middleware');
const usageLimit = require('./middlewares/usageLimit.middleware');

// 🔒 Whitelist CORS configuration
const allowedOrigins = [
  process.env.FRONTEND_ORIGIN || 'http://localhost:5173',
  'http://localhost:80',
  'http://localhost:3000'
];

app.use(cors({
  origin: function (origin, callback) {
    if (!origin || allowedOrigins.includes(origin)) {
      return callback(null, true);
    }
    return callback(new Error('Blocked by CORS policy for FileWiz Backend'));
  },
  credentials: true
}));

// 🛡️ API Abuse Rate Limiting
const processingRateLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: process.env.NODE_ENV === 'test' ? 1000 : 30, // 30 heavy processing requests per minute per IP
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Processing rate limit exceeded. Please wait a moment before initiating more operations.' }
});

app.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  next();
});

const fs = require('fs');

app.get('/', (req, res) => {
  res.send('FileWiz Backend API is running.');
});

const { router: jobRouter, jobQueueInstance } = require('./routes/jobRouter');

// Health check endpoint for Kubernetes probes
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'filewiz-backend' });
});

// Deep health check & Kubernetes Liveness / Readiness Probes
app.get('/health/liveness', (req, res) => {
  res.json({ status: 'healthy', check: 'liveness', uptime: process.uptime() });
});

app.get('/health/readiness', (req, res) => {
  const queueHealth = jobQueueInstance.checkHealth();
  res.json({ status: 'healthy', check: 'readiness', queue: queueHealth });
});

app.get('/health/deep', (req, res) => {
  const queueHealth = jobQueueInstance.checkHealth();
  res.json({
    status: 'healthy',
    service: 'filewiz-backend',
    uptime: process.uptime(),
    queue: queueHealth
  });
});

// Mount Asynchronous Job Processing Queue
app.use(jobRouter);

// 🔒 SECURED PROCESSING ROUTES: Enforce authentication and rate limiting across all operations
app.use('/peek', isAuthenticated, peekRouter);

app.use("/compress/pdf", isAuthenticated, processingRateLimiter, usageLimit, compressRouter);

app.use("/compress/ppt", isAuthenticated, processingRateLimiter, usageLimit, compressPPTRouter);

app.use("/split/pdf", isAuthenticated, processingRateLimiter, usageLimit, splitRouter);

app.use('/redaction', isAuthenticated, processingRateLimiter, usageLimit, redactionRouter);

app.use("/encrypt", isAuthenticated, processingRateLimiter, encryptRouter);

app.use("/repair", isAuthenticated, processingRateLimiter, usageLimit, repairRouter);

app.use("/convert", isAuthenticated, processingRateLimiter, usageLimit, convertRouter);

const server = http.createServer(app);

// Ensure temp directories exist
const tempUploads = path.join(rootDir, 'temp', 'uploads');
const tempOutputs = path.join(rootDir, 'temp', 'outputs');
if (!fs.existsSync(tempUploads)) fs.mkdirSync(tempUploads, { recursive: true });
if (!fs.existsSync(tempOutputs)) fs.mkdirSync(tempOutputs, { recursive: true });

server.listen(PORT, async () => {
  if (process.env.MONGODB_URI) {
    try {
      await mongoConnect();
    } catch (err) {
      console.warn("MongoDB connection warning for backend:", err.message);
    }
  }
  console.log(`FileWiz Backend Service running on port ${PORT}`);
});