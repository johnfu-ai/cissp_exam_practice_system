// Login page (FR-CLIENT-07: username/password over the shared account system).
const api = require("../../lib/request");
const i18n = require("../../lib/i18n");

Page({
  data: { email: "", password: "", busy: false, error: "" },
  t(key) { return i18n.t(key); },
  onEmail(e) { this.setData({ email: e.detail.value }); },
  onPassword(e) { this.setData({ password: e.detail.value }); },
  async submit() {
    if (!this.data.email || !this.data.password || this.data.busy) return;
    this.setData({ busy: true, error: "" });
    try {
      await api.login(this.data.email, this.data.password);
      wx.reLaunch({ url: "/pages/papers/index" });
    } catch (err) {
      this.setData({
        busy: false,
        error: (err.detail && err.detail.detail) || "login failed",
      });
    }
  },
});
