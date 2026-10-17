
const EventEmitter = require('events');

class JobQueue extends EventEmitter {
    constructor(concurrency = 10) {
        super();
        this.concurrency = concurrency;
        this.queue = [];
        this.processing = new Map(); // jobId -> { status, progress, data }
        this.jobIdCounter = 0;
    }

    async addJob(jobType, jobData) {
        const jobId = this.jobIdCounter++;
        const job = { jobId, jobType, jobData, status: 'PENDING' };
        this.queue.push(job);
        this.processing.set(jobId, { status: 'PENDING', progress: 0, data: null });
        this.emit('jobQueued', job);
        this.processQueue();
        return jobId;
    }

    async processQueue() {
        while (this.processing.size < this.concurrency && this.queue.length > 0) {
            const job = this.queue.shift();
            if (!job) continue;

            this.processing.set(job.jobId, { ...this.processing.get(job.jobId), status: 'PROCESSING' });
            this.emit('jobProcessing', job);

            try {
                // Simulate job processing
                await this.runJob(job);
                // If runJob completes without error, it will update status to COMPLETED or FAILED
            } catch (error) {
                this.updateJobStatus(job.jobId, 'FAILED', { error: error.message });
            }
        }
    }

    async runJob(job) {
        // This is where the actual job logic would be implemented based on jobType
        const workDelay = process.env.NODE_ENV === 'test' ? 80 : 1500;
        await new Promise(resolve => setTimeout(resolve, workDelay)); // Simulate work

        if (job.jobData && job.jobData.shouldFail) {
            throw new Error('Simulated job failure');
        }

        this.updateJobStatus(job.jobId, 'COMPLETED', { result: `Job ${job.jobId} processed successfully` });
    }

    updateJobStatus(jobId, status, data = null) {
        if (this.processing.has(jobId)) {
            const currentJobState = this.processing.get(jobId);
            this.processing.set(jobId, { ...currentJobState, status, data });
            this.emit('jobStatusUpdate', { jobId, status, data });

            if (status === 'COMPLETED' || status === 'FAILED') {
                // Optionally remove from processing after a delay or when GC\'d
                // For simplicity here, we leave it and rely on the overall health check to manage it
                // or a dedicated cleanup mechanism if memory becomes an issue.
                // setTimeout(() => {
                //     this.processing.delete(jobId);
                //     this.emit('jobFinished', jobId);
                //     this.processQueue(); // Try to process next job
                // }, 60000); // Remove after 1 minute
            }
        }
    }

    cancelJob(jobId) {
        if (this.processing.has(jobId)) {
            const jobState = this.processing.get(jobId);
            if (jobState.status === 'PROCESSING' || jobState.status === 'PENDING') {
                jobState.status = 'CANCELLED';
                this.processing.set(jobId, jobState);
                this.emit('jobCancelled', { jobId, status: 'CANCELLED' });
                return true; // Indicate cancellation was successful
            }
        }
        return false; // Indicate job not found or not in a cancellable state
    }

    getJobStatus(jobId) {
        return this.processing.get(jobId) || { status: 'NOT_FOUND' };
    }

    // Method to ensure queue workers are always available or to report health
    checkHealth() {
        // This method can be expanded to check worker health, active connections, etc.
        // For now, it indicates if the queue is generally operational.
        return {
            isHealthy: true, // Assume healthy if running, more checks can be added
            processingCount: this.processing.size,
            queueLength: this.queue.length,
            concurrency: this.concurrency
        };
    }

     // Cleanup method to be called on shutdown
    async gracefulShutdown() {
        console.log('Shutting down job queue...');
        // Clear the queue and stop processing new jobs
        this.queue = [];
        // Optionally, attempt to cancel or save state of processing jobs
        for (const [jobId, jobState] of this.processing.entries()) {
            if (jobState.status === 'PROCESSING') {
                console.log(`Job ${jobId} was in processing state, not explicitly cancelled.`);
                // In a real-world scenario, you might want to implement cancellation tokens or save state
            }
        }
        this.processing.clear();
        console.log('Job queue shut down complete.');
    }
}

module.exports = { JobQueue };
