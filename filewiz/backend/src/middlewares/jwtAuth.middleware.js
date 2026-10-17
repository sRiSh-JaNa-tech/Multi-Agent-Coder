const { verifyToken } = require("../utils/jwt");

module.exports = function jwtAuth(req, res, next) {
  const token = req.cookies.auth_token;

  if (!token) {
    return res.redirect("/auth/login");
  }

  try {
    const decoded = verifyToken(token);
    req.user = decoded; 
    next();
  } catch (err) {
    res.clearCookie("auth_token");
    return res.redirect("/auth/login");
  }
};