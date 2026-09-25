// App entry: i18n init + login guard helper (FR-CLIENT-02).
const i18n = require("./lib/i18n");
const api = require("./lib/request");

App({
  onLaunch() {
    i18n.init();
    if (!api.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/index" });
    }
  },
  globalData: {
    locale: i18n.getLocale(),
    languageMode: "bilingual",
  },
});
