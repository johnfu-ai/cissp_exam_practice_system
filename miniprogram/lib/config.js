// API base configuration for the WeChat mini program (FR-CLIENT-01).
//
// Dev: point WeChat DevTools at your machine's backend and enable
// 「不校验合法域名」(details > local settings), or set the base explicitly.
// Prod: the domain must be TLS and whitelisted in the mini program console
// (request 合法域名).

let overrideBase = null;

function detectDefaultBase() {
  // envVersion: 'develop' | 'trial' | 'release' (wx.getAccountInfoSync)
  try {
    const wx = global.wx;
    if (wx && wx.getAccountInfoSync) {
      const env = wx.getAccountInfoSync().miniProgram.envVersion;
      if (env === "release") {
        return "https://api.example.com"; // TODO: set the production origin
      }
    }
  } catch (e) {
    /* fall through */
  }
  return "http://localhost:8000";
}

function getApiBase() {
  return overrideBase || detectDefaultBase();
}

function setApiBase(base) {
  overrideBase = base;
}

module.exports = { getApiBase, setApiBase };
