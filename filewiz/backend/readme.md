# <p align="center"><img src="src/public/assets/open-folder.png" width="100" height="100" alt="FileWiz Logo"><br>FileWiz</p>

<p align="center">
  <strong>The Ultimate Universal File Utility Engine</strong><br>
  <em>Compress, Extract, Optimize, and Secure your files through a high-performance, unified web interface.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Node.js-v18+-green.svg" alt="Node.js">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Database-MongoDB-darkgreen.svg" alt="MongoDB">
  <img src="https://img.shields.io/badge/Processing-FFMPEG-orange.svg" alt="FFMPEG">
  <img src="https://img.shields.io/badge/License-ISC-yellow.svg" alt="License ISC">
</p>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Core Features](#-core-features)
- [System Architecture](#-system-architecture)
- [Installation & Setup](#-installation--setup)
- [Security & Authentication](#-security--authentication)
- [Technology Stack](#-technology-stack)
- [Support](#-support)

---

## 🌟 Overview

**FileWiz** is a production-grade, full-stack utility platform designed to handle the most common yet complex file operations directly in the browser. Instead of juggling multiple desktop applications or untrusted online tools, FileWiz offers a secure, fast, and unified environment for managing archives, optimizing PDFs, and compressing media.

Built with a hybrid architecture of **Node.js** for orchestration and **Python** for heavy-duty processing, FileWiz ensures that resource-intensive tasks are handled with maximum efficiency and zero permanent footprint.

---

## 🚀 Core Features

-   **📦 Advanced ZIP Management**: Peek inside ZIP archives, edit contents, and download specific files without ever needing to extract the full archive locally.
-   **📄 Precision PDF Optimization**: Lossless and high-compression modes powered by 7-Zip (`7za`) to drastically reduce file size while maintaining readability.
-   **📽️ Multi-Level PPT Compression**: Customizable compression levels (Normal vs. Extreme) including the ability to strip heavy images for maximum portability.
-   **🎥 Universal Media Compression**: Integrated FFMPEG pipelines for optimizing video and audio files without losing perceived quality.
-   **🔐 Integrated Authentication**: Secure user accounts with session management and MongoDB persistence for a personalized experience.
-   **🧹 Auto-Cleanup Pipeline**: A robust temporary file management system that ensures user data is strictly isolated and automatically wiped after processing.

---

## 🏗️ System Architecture

FileWiz follows a modular processing pipeline:

1.  **Orchestration Layer (Node.js/Express)**: Handles user requests, file uploads, authentication, and session state. It acts as the gatekeeper for the system.
2.  **Logic Engine (Python)**: Specialized scripts handle format-specific tasks like OCR (Tesseract), PDF manipulation (PyMuPDF/PyPDF2), and document conversion.
3.  **Tooling Core (7-Zip/FFMPEG)**: Low-level system binaries perform the heavy lifting for compression and structural repair.
4.  **Persistence Layer (MongoDB)**: Stores user credentials and profile metadata, while binary data remains temporary and ephemeral.

---

## 🛠️ Installation & Setup

### Prerequisites
-   **Node.js v18+**
-   **Python 3.10+**
-   **7-Zip (`7za` bundled via `7zip-bin` or system PATH)**
-   **FFMPEG** (Must be in system PATH)

### Quick Start

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/sRiSh-JaNa-tech/FileWiz.git
    cd FileWiz
    ```
2.  **Install Node Dependencies**:
    ```bash
    npm install
    ```
3.  **Setup Python Environment**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment**:
    Create a `.env` file in the root directory:
    ```env
    MONGODB_URI=your_mongodb_connection_string
    PORT=3000
    ```
5.  **Run the Server**:
    ```bash
    npm run dev
    ```

---

## 🛡️ Security & Authentication

FileWiz prioritizes user data integrity and security:
-   **Bcrypt Encryption**: All user passwords are salted and hashed using industry-standard rounds.
-   **Session Isolation**: Secure `express-session` implementation ensures that users can only access their own processing contexts.
-   **Ephemeral Storage**: Files are processed in isolated `temp` directories and cleared periodically via an automated cleanup service.

---

## 🛠️ Technology Stack

-   **Frontend**: HTML5, Vanilla CSS (Premium UI), EJS Templating
-   **Backend**: Node.js, Express.js
-   **Database**: MongoDB (with Mongoose-like native drivers)
-   **Processing Libs**: 
    -   *Python*: PyMuPDF, PyPDF2, Pillow, Pytesseract, pdf2docx
    -   *System*: 7-Zip (7za), FFMPEG
-   **Authentication**: Bcrypt, Express-Session, Cookie-Parser

---

## 🤝 Support

If you find FileWiz helpful, please consider giving the repository a ⭐ on GitHub!

<p align="center">Built for Developers & Power Users</p>
