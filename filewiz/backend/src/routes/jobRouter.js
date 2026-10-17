const express = require('express');
const router = express.Router();
const { JobQueue } = require('../services/jobQueue');

// Assume jobQueue is initialized elsewhere and passed or accessed globally
// For demonstration, we'll create a simple instance here. In a real app, 
// this would likely be managed by the main application setup.
const jobQueue = new JobQueue(5); // Example with concurrency of 5

/**
 * @swagger
 * /api/v1/jobs: 
 *   post: 
 *     summary: Submits a new file operation job to the queue.
 *     requestBody: 
 *       required: true
 *       content: 
 *         application/json:
 *           schema:
 *             type: object
 *             properties: 
 *               jobType: 
 *                 type: string
 *                 description: The type of job to perform (e.g., 'FILE_CONVERSION', 'THUMBNAIL_GENERATION').
 *               jobData: 
 *                 type: object
 *                 description: Data required for the job (e.g., filePath, options).
 *     responses: 
 *       201: 
 *         description: Job created successfully.
 *         content: 
 *           application/json:
 *             schema: 
 *               type: object
 *               properties: 
 *                 message: 
 *                   type: string
 *                 jobId: 
 *                   type: integer
 *       400: 
 *         description: Bad request (e.g., missing parameters).
 */
// Handlers for job submission
const handleAddJob = async (req, res) => {
    const jobType = req.body.jobType || req.body.type || 'DOCUMENT_PROCESSING';
    const jobData = req.body.jobData || req.body.data || req.body;

    if (!jobData) {
        return res.status(400).json({ message: 'Missing jobData in request body.' });
    }

    try {
        const jobId = await jobQueue.addJob(jobType, jobData);
        res.status(201).json({
            message: 'Job submitted successfully.',
            jobId: jobId,
            id: jobId,
            status: 'PENDING'
        });
    } catch (error) {
        console.error('Failed to add job to queue:', error);
        res.status(500).json({ message: 'Internal server error while submitting job.' });
    }
};

// Handlers for job status lookup
const handleGetStatus = async (req, res) => {
    const jobId = parseInt(req.params.jobId, 10);

    if (isNaN(jobId)) {
        return res.status(400).json({ message: 'Invalid Job ID format.' });
    }

    const jobStatus = jobQueue.getJobStatus(jobId);

    if (jobStatus.status === 'NOT_FOUND') {
        return res.status(404).json({ message: `Job with ID ${jobId} not found.` });
    }

    res.status(200).json({
        id: jobId,
        jobId: jobId,
        status: jobStatus.status,
        progress: jobStatus.progress || 0,
        data: jobStatus.data || null
    });
};

router.post('/api/v1/jobs', handleAddJob);
router.post('/jobs', handleAddJob);

router.get('/api/v1/jobs/:jobId/status', handleGetStatus);
router.get('/api/v1/jobs/:jobId', handleGetStatus);
router.get('/jobs/:jobId/status', handleGetStatus);
router.get('/jobs/:jobId', handleGetStatus);

// Export the router and the jobQueue instance if needed elsewhere, or manage its lifecycle in server.js
module.exports = {
    router,
    // Export jobQueue if it needs to be accessed directly for health checks etc.
    // In a more complex app, you might have a central registry or dependency injection
    jobQueueInstance: jobQueue 
};
