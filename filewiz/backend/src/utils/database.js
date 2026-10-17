const mongodb = require("mongodb");
const MongoClient = mongodb.MongoClient;
let _db;

const url = process.env.MONGODB_URI;

const mongoConnect = async () => {
    try {
        const client = new MongoClient(url, {
            serverSelectionTimeoutMS: 5000,
        });

        await client.connect();
        console.log("Connected to MongoDB");

        _db = client.db("authApp"); // DB name comes from URI
    } catch (err) {
        console.error("MongoDB connection failed", err);
        throw err;
    }
};

const getDb = () => {
    if (!_db) {
        throw new Error("No database found");
    }
    return _db;
};

module.exports = { mongoConnect, getDb };