const os = require('os');

class ConcurrencyLimiter {
  constructor(concurrencyLimit = os.cpus().length || 4) {
    this.limit = concurrencyLimit;
    this.activeCount = 0;
    this.queue = [];
  }

  async run(taskFn) {
    // If we are at the limit, wait in the queue
    if (this.activeCount >= this.limit) {
      await new Promise(resolve => this.queue.push(resolve));
    }

    this.activeCount++;

    try {
      // Execute the heavy task
      return await taskFn();
    } finally {
      this.activeCount--;
      // Dequeue the next task if any
      if (this.queue.length > 0) {
        const nextResolve = this.queue.shift();
        nextResolve();
      }
    }
  }
}

// Export a singleton instance with limit based on CPU cores
// Default limit: up to CPU cores, but cap at a max of 4 to prevent total starvation on large instances
const maxConcurrent = Math.min(os.cpus().length, 4) || 2;
const globalLimiter = new ConcurrencyLimiter(maxConcurrent);

module.exports = {
  ConcurrencyLimiter,
  globalLimiter
};
