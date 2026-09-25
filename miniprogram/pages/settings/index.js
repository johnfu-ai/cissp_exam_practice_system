// Settings: interface language, question language mode, logout (FR-SET).
const api = require("../../lib/request");
const papers = require("../../lib/papers");
const i18n = require("../../lib/i18n");
const storage = require("../../lib/storage");

Page({
  data: { locale: "zh", languageMode: "bilingual" },
  t(key) { return i18n.t(key); },
  onShow() {
    if (!api.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const saved = storage.getItem(storage.KEYS.MODE);
    this.setData({
      locale: i18n.getLocale(),
      languageMode: saved || "bilingual",
    });
  },
  async setLocale(e) {
    const locale = e.currentTarget.dataset.locale;
    i18n.setLocale(locale);
    this.setData({ locale });
  },
  async setMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ languageMode: mode });
    storage.setItem(storage.KEYS.MODE, mode);
    try {
      await papers.updatePreferences({ language_mode: mode });
    } catch (err) { /* local preference already saved */ }
  },
  onCurrent(e) { this.setData({ currentPassword: e.detail.value }); },
  onNew(e) { this.setData({ newPassword: e.detail.value }); },
  async changePassword() {
    const { currentPassword, newPassword } = this.data;
    if (!currentPassword || !newPassword) return;
    try {
      await papers.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      this.setData({ currentPassword: "", newPassword: "", pwMsg: "ok" });
    } catch (err) {
      this.setData({ pwMsg: "failed" });
    }
  },

  async logout() {
    api.clearSession();
    wx.reLaunch({ url: "/pages/login/index" });
  },
});
