// Thin wx storage adapter so lib modules stay unit-testable (mock global wx).

const KEYS = {
  ACCESS: "cissp_access",
  REFRESH: "cissp_refresh",
  USER: "cissp_user",
  LOCALE: "cissp_locale",
  MODE: "cissp_language_mode",
};

function getWx() {
  return global.wx;
}

function setItem(key, value) {
  getWx().setStorageSync(key, value);
}

function getItem(key) {
  return getWx().getStorageSync(key);
}

function removeItem(key) {
  getWx().removeStorageSync(key);
}

module.exports = { KEYS, setItem, getItem, removeItem };
