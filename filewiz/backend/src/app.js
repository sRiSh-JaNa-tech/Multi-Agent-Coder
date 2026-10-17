require('dotenv').config();
const path = require('path');
const rootDir = require('./utils/pathUtils');
const express = require('express');
const session = require("express-session");
const cookieparser = require('cookie-parser');
const helmet = require('helmet');
const cleanupWorkspaces = require('./services/workspaceCleanup');

// Periodic workspace cleanup
setInterval(cleanupWorkspaces, 60 * 60 * 1000);
cleanupWorkspaces();

const app = express();

// 🛡️ Apply HTTP Security Headers
app.use(helmet({
  contentSecurityPolicy: false // Allows API to serve appropriate resources
}));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieparser());
app.use(express.static(path.join(rootDir, 'public')));

// 🔒 CRITICAL: /temp static directory serving REMOVED to prevent public exfiltration

// Session management with secret enforcement
const sessionSecret = process.env.SESSION_SECRET || (process.env.NODE_ENV === 'production' ? null : 'filewiz-dev-session-secret');
if (process.env.NODE_ENV === 'production' && (!sessionSecret || sessionSecret === 'super-secret-key' || sessionSecret === 'filewiz-dev-session-secret')) {
  throw new Error('FATAL SECURITY ERROR: SESSION_SECRET must be configured with a strong secret in production environment.');
}

app.use(
  session({
    name: "filewiz-session",
    secret: sessionSecret || "filewiz-dev-session-secret",
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 30 * 60 * 1000,
    },
  })
);

app.use((req, res, next) => {
  req.user = req.session.user || null;
  res.locals.user = req.user;
  next();
});

module.exports = app;