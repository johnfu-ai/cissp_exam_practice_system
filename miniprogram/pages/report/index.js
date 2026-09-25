// Exam report + review (FR-PAPER-06 / FR-ESSAY-03) with essay self-assessment.
const papers = require("../../lib/papers");
const i18n = require("../../lib/i18n");

Page({
  data: { report: null, review: [], openPosition: -1, loading: true },
  t(key) { return i18n.t(key); },
  async onLoad(options) {
    try {
      const [report, review] = await Promise.all([
        papers.getExamReport(options.sessionId),
        papers.getExamReview(options.sessionId),
      ]);
      this.setData({ report, review, loading: false });
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: "load failed", icon: "none" });
    }
  },
  toggle(e) {
    const position = e.currentTarget.dataset.position;
    this.setData({
      openPosition: this.data.openPosition === position ? -1 : position,
    });
  },
  async assess(e) {
    const { position, correct } = e.currentTarget.dataset;
    try {
      await papers.examSelfAssess(
        this.data.report.session_id, position, correct === "1",
      );
      const review = await papers.getExamReview(this.data.report.session_id);
      const report = await papers.getExamReport(this.data.report.session_id);
      this.setData({ review, report });
    } catch (err) {
      wx.showToast({ title: "failed", icon: "none" });
    }
  },
  goPapers() { wx.switchTab({ url: "/pages/papers/index" }); },
});
