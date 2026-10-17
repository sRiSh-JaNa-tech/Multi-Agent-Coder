const bcrypt = require('bcryptjs');

const getDatabaseUrl = () => {
    return process.env.DATABASE_SERVICE_URL || 'http://localhost:5000';
};

const getInternalHeaders = (extra = {}) => {
    return {
        'x-internal-service-key': process.env.INTERNAL_SERVICE_KEY || 'filewiz-internal-db-secret',
        ...extra
    };
};

class User {
    constructor(name, age, email, password) {
        this.name = name;
        this.age = age ? parseInt(age, 10) : null;
        this.email = email ? email.toLowerCase().trim() : '';
        this.password = password;
        this.createdAt = new Date().toISOString();
    }

    /**
     * Save user data into SQLite via the dedicated Database Service
     */
    async create() {
        try {
            const hashed = await bcrypt.hash(this.password, 10);
            this.password = hashed;

            const res = await fetch(`${getDatabaseUrl()}/users`, {
                method: 'POST',
                headers: getInternalHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    name: this.name,
                    age: this.age,
                    email: this.email,
                    password: this.password,
                    createdAt: this.createdAt
                })
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Failed to create user in database');
            }

            return data.user;
        } catch (err) {
            console.error("[AUTH SERVICE] User creation failed:", err.message);
            throw err;
        }
    }

    /**
     * Retrieve user by email from the dedicated Database Service
     */
    static async findByEmail(email, includePassword = false) {
        const normalizedEmail = email ? email.toLowerCase().trim() : '';
        try {
            const res = await fetch(
                `${getDatabaseUrl()}/users/email/${encodeURIComponent(normalizedEmail)}?includePassword=${includePassword}`,
                {
                    headers: getInternalHeaders()
                }
            );
            if (res.status === 404) {
                return null;
            }
            const data = await res.json();
            return data.user || null;
        } catch (err) {
            console.error("[AUTH SERVICE] Error retrieving user by email from Database service:", err.message);
            throw err;
        }
    }

    /**
     * Retrieve user by ID from the dedicated Database Service
     */
    static async findById(id) {
        try {
            const res = await fetch(`${getDatabaseUrl()}/users/id/${encodeURIComponent(id)}`, {
                headers: getInternalHeaders()
            });
            if (res.status === 404) {
                return null;
            }
            const data = await res.json();
            return data.user || null;
        } catch (err) {
            console.error("[AUTH SERVICE] Error retrieving user by ID from Database service:", err.message);
            throw err;
        }
    }

    /**
     * Retrieve all users from the dedicated Database Service
     */
    static async getAll() {
        try {
            const res = await fetch(`${getDatabaseUrl()}/users`, {
                headers: getInternalHeaders()
            });
            const data = await res.json();
            return data.users || [];
        } catch (err) {
            console.error("[AUTH SERVICE] Error retrieving all users from Database service:", err.message);
            throw err;
        }
    }

    /**
     * Authenticate and retrieve user data
     */
    static async login(email, password) {
        const user = await this.findByEmail(email, true);
        if (!user || !user.password) {
            return null;
        }

        const isValid = await bcrypt.compare(password, user.password);
        if (!isValid) {
            return null;
        }

        const { password: _, ...userWithoutPassword } = user;
        return userWithoutPassword;
    }
}

module.exports = User;
