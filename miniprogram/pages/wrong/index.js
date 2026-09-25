// Wrong book (错题集) — FR-WRONG-02..05: three tabs + re-practice + mastered.
const papers = require("../../lib/papers");
const api = require("../../lib/request");
const i18n = require("../../lib/i18n");

Page({
  data: { tab: "wrong", items: [], loading: true, openId: "" },
  tabs: [
    { key: "wrong", labelKey: "tabWrongTitle" },
    { key: "bookmarked", labelKey: "tabBookmarked" },
    { key: "flagged", labelKey: "tabFlagged" },
  ],
  t(key) { return i18n.t(key); },
  onShow() {
    if (!api.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.refresh();
  },
  async refresh() {
    this.setData({ loading: true });
    try {
      const data = await papers.getWrongBook(this.data.tab, "");
      const items = (data.items || []).map((x) => ({
        ...x,
        wrongText: i18n.t("wrongNTimes", { count: x.wrong_count }),
        papersText: (x.papers || []).join("、"),
      }));
      this.setData({ items, loading: false });
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: "load failed", icon: "none" });
    }
  },
  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.tab, openId: "" });
    this.refresh();
  },
  toggle(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ openId: this.data.openId === id ? "" : id });
  },
  async markMastered(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await papers.setQuestionState(id, { is_mastered: true });
      this.refresh();
    } catch (err) {
      wx.showToast({ title: "failed", icon: "none" });
    }
  },
  async rePractice() {
    try {
      const session = await papers.wrongBookPractice({ count: 50 });
      wx.navigateTo({
        url: `/pages/play/index?sessionId=${session.id}&kind=practice`,
      });
    } catch (err) {
      wx.showToast({ title: "empty", icon: "none" });
    }
  },
});
