// Paper library (题库) — FR-PAPER-03.
const papers = require("../../lib/papers");
const api = require("../../lib/request");
const i18n = require("../../lib/i18n");

function decorate(p, t) {
  const items = p.items || [];
  return items.map((x) => ({
    ...x,
    countText: t("questionCount", { count: x.question_count }),
    durationText: x.duration_minutes ? t("duration", { minutes: x.duration_minutes }) : "",
    scoreText: t("score", { score: x.total_score }),
  }));
}

Page({
  data: { papers: [], loading: true, error: "" },
  t(key) { return i18n.t(key); },
  onShow() {
    if (!api.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.refresh();
  },
  async refresh() {
    this.setData({ loading: true, error: "" });
    try {
      const data = await papers.listPapers();
      this.setData({ papers: decorate(data, i18n.t), loading: false });
    } catch (err) {
      this.setData({ loading: false, error: String((err.detail && err.detail.detail) || err.status || err) });
    }
  },
  async start(e) {
    const { id, mode } = e.currentTarget.dataset;
    try {
      const session = await papers.createPaperSession(id, mode);
      wx.navigateTo({
        url: `/pages/play/index?sessionId=${session.id}&kind=${mode}`,
      });
    } catch (err) {
      wx.showToast({ title: "failed", icon: "none" });
    }
  },
});
