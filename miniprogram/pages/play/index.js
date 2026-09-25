// Paper player (FR-PAPER-05/07): timer, answer sheet, bilingual toggle,
// essay textarea + self-assessment, exam auto-save on navigation + submit.
const papers = require("../../lib/papers");
const i18n = require("../../lib/i18n");
const sheetLib = require("../../lib/answer-sheet");

const MODE_CYCLE = { en: "zh", zh: "bilingual", bilingual: "en" };

function decorateQuestion(q, mode) {
  return {
    ...q,
    stemText: pickText(q.stem, mode),
    options: (q.options || []).map((o) => ({
      ...o,
      label: String.fromCharCode(65 + o.order_index) + ".",
      text: pickText(o.content, mode),
    })),
    isEssay: q.question_type === "essay",
  };
}

function pickText(loc, mode) {
  if (!loc) return "";
  if (mode === "en") return loc.en || loc.zh || "";
  if (mode === "zh") return loc.zh || loc.en || "";
  return [loc.en, loc.zh].filter(Boolean).join("\n");
}

Page({
  data: {
    sessionId: "",
    kind: "practice",
    position: 0,
    total: 0,
    q: null,
    mode: "bilingual",
    modeLabel: "EN/中文",
    selection: [],
    essayText: "",
    result: null,
    sheet: null,
    counts: null,
    cells: [],
    clock: "00:00",
    finished: false,
    summary: null,
    deadlineEpoch: 0,
    loading: true,
  },

  t(key) { return i18n.t(key); },

  onLoad(options) {
    this.sheet = sheetLib.emptySheet();
    this.setData({
      sessionId: options.sessionId,
      kind: options.kind === "exam" ? "exam" : "practice",
    });
    this.startedEpoch = Date.now();
    this.loadQuestion(0);
    this.timer = setInterval(() => this.tick(), 1000);
  },
  onUnload() {
    if (this.timer) clearInterval(this.timer);
  },

  tick() {
    const now = Date.now();
    if (this.data.kind === "exam" && this.data.deadlineEpoch) {
      const remaining = sheetLib.remainingMs(this.data.deadlineEpoch, now);
      this.setData({ clock: sheetLib.formatClock(remaining) });
      if (remaining <= 0 && !this.data.finished) this.submitPaper();
    } else {
      this.setData({ clock: sheetLib.formatClock(now - this.startedEpoch) });
    }
  },

  renderSheet(total) {
    const cells = [];
    for (let i = 0; i < total; i += 1) {
      cells.push({ position: i, status: sheetLib.cellStatus(this.sheet, i) });
    }
    this.setData({ cells, counts: sheetLib.sheetCounts(this.sheet, total) });
  },

  async loadQuestion(position) {
    this.setData({ loading: true });
    const fetcher =
      this.data.kind === "exam" ? papers.getExamQuestion : papers.getPracticeQuestion;
    try {
      const q = await fetcher(this.data.sessionId, position);
      const prev = q.previous_answer || null;
      if (this.data.kind === "exam" && !this.data.deadlineEpoch && q.time_remaining_ms) {
        this.setData({ deadlineEpoch: Date.now() + q.time_remaining_ms });
      }
      this.setData({
        position,
        total: q.total,
        q: decorateQuestion(q, this.data.mode),
        selection: (prev && prev.selected) || [],
        essayText: (prev && prev.text) || "",
        result: null,
        loading: false,
      });
      if (prev && ((prev.selected && prev.selected.length) || prev.text)) {
        this.sheet.answered[position] = true;
      }
      if (prev && prev.is_correct === false) this.sheet.wrong[position] = true;
      this.renderSheet(q.total);
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: "load failed", icon: "none" });
    }
  },

  toggleMode() {
    // pure client state — never advances or submits (FR-LANG-06 invariant)
    const mode = MODE_CYCLE[this.data.mode];
    this.setData({
      mode,
      modeLabel: mode === "en" ? "EN" : mode === "zh" ? "中文" : "EN/中文",
      q: this.data.q ? decorateQuestion(this.data.q, mode) : null,
    });
  },

  selectOption(e) {
    if (this.data.kind === "practice" && this.data.result) return;
    const idx = e.currentTarget.dataset.index;
    let selection = this.data.selection || [];
    if (this.data.q.question_type === "multiple_choice") {
      selection = selection.includes(idx)
        ? selection.filter((x) => x !== idx)
        : [...selection, idx].sort((a, b) => a - b);
    } else {
      selection = [idx];
    }
    this.setData({ selection });
  },

  onEssay(e) {
    this.setData({ essayText: e.detail.value });
  },

  async commitExam(position) {
    if (this.data.kind !== "exam") return;
    const isEssay = this.data.q.isEssay;
    await papers.submitExamAnswer(this.data.sessionId, {
      position,
      selected: isEssay ? [] : this.data.selection,
      ...(isEssay ? { answer_text: this.data.essayText } : {}),
      started_at: new Date().toISOString(),
    });
    const hasAnswer = isEssay
      ? this.data.essayText.trim().length > 0
      : (this.data.selection || []).length > 0;
    this.sheet.answered[position] = hasAnswer;
    this.renderSheet(this.data.total);
  },

  async goto(e) {
    const position = e.currentTarget.dataset.position;
    if (position < 0 || position >= this.data.total) return;
    if (this.data.kind === "exam" && !this.data.finished) {
      try {
        await this.commitExam(this.data.position);
      } catch (err) { /* next save retries */ }
    }
    this.loadQuestion(position);
  },

  async submitAnswer() {
    const isEssay = this.data.q.isEssay;
    try {
      const result = await papers.submitPracticeAnswer(this.data.sessionId, {
        position: this.data.position,
        selected: isEssay ? [] : this.data.selection,
        ...(isEssay ? { answer_text: this.data.essayText } : {}),
        started_at: new Date().toISOString(),
      });
      this.sheet.answered[this.data.position] = true;
      if (result.is_correct === false) this.sheet.wrong[this.data.position] = true;
      this.setData({ result: { ...result, reference: result.reference_answer } });
      this.renderSheet(this.data.total);
    } catch (err) {
      wx.showToast({ title: "submit failed", icon: "none" });
    }
  },

  async assess(e) {
    const correct = e.currentTarget.dataset.correct === "1";
    try {
      await papers.practiceSelfAssess(this.data.sessionId, this.data.position, correct);
      this.setData({ result: { ...this.data.result, is_correct: correct } });
      if (!correct) {
        this.sheet.wrong[this.data.position] = true;
        this.renderSheet(this.data.total);
      }
    } catch (err) {
      wx.showToast({ title: "failed", icon: "none" });
    }
  },

  toggleFlag() {
    const position = this.data.position;
    const next = !this.sheet.flagged[position];
    this.sheet.flagged[position] = next;
    this.renderSheet(this.data.total);
    if (this.data.q) {
      papers.setQuestionState(this.data.q.question_id, {
        is_flagged_review: next,
      }).catch(() => {});
    }
  },

  async submitPaper() {
    if (this.data.finished) return;
    if (this.data.kind === "exam") {
      try {
        await this.commitExam(this.data.position);
      } catch (err) { /* finish judges saved answers */ }
      await papers.finishExam(this.data.sessionId);
      wx.redirectTo({
        url: `/pages/report/index?sessionId=${this.data.sessionId}`,
      });
      return;
    }
    const summary = await papers.finishPractice(this.data.sessionId);
    if (this.timer) clearInterval(this.timer);
    this.setData({
      finished: true,
      summary: {
        answered: summary.answered_count,
        correct: summary.correct_count,
        accuracy: Math.round((summary.accuracy || 0) * 100),
      },
    });
  },

  goWrongBook() {
    wx.switchTab({ url: "/pages/wrong/index" });
  },
  goPapers() {
    wx.switchTab({ url: "/pages/papers/index" });
  },
});
