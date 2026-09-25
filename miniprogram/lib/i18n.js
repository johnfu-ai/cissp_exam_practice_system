// UI i18n for the mini program (en/zh), mirroring the web dictionary subset
// used by the learner flow (FR-I18N, client-side only).

const storage = require("./storage");

const DICTS = {
  en: {
    appName: "CISSP Papers",
    tabPapers: "Papers",
    tabWrong: "Wrong",
    tabMe: "Me",
    login: "Log in",
    email: "Email",
    password: "Password",
    logout: "Log out",
    questionCount: "{count} questions",
    score: "{score} pts",
    duration: "{minutes} min",
    startPractice: "Practice",
    startExam: "Exam",
    practiceMode: "Practice",
    examMode: "Exam",
    elapsed: "Elapsed",
    remaining: "Remaining",
    prev: "Previous",
    next: "Next",
    submit: "Submit",
    submitPaper: "Submit paper",
    finish: "Finish",
    answered: "Answered",
    wrong: "Wrong",
    unanswered: "Unanswered",
    flagged: "Flagged",
    correct: "Correct",
    incorrect: "Incorrect",
    rationale: "Explanation",
    referenceAnswer: "Reference answer",
    iWasRight: "I got it right",
    iWasWrong: "I got it wrong",
    tabWrongTitle: "My wrongs",
    tabBookmarked: "Bookmarked",
    tabFlagged: "Flagged",
    rePractice: "Re-practice",
    markMastered: "Mark mastered",
    mastered: "Mastered",
    wrongNTimes: "Wrong {count}x",
    viewAnswer: "Explanation",
    empty: "Nothing here yet",
    reportTitle: "Exam report",
    passed: "Passed",
    failed: "Not passed",
    interfaceLanguage: "Interface language",
    contentLanguage: "Question language",
    changePassword: "Change password",
    settings: "Settings",
    loading: "Loading...",
  },
  zh: {
    appName: "CISSP 刷题",
    tabPapers: "题库",
    tabWrong: "错题",
    tabMe: "我的",
    login: "登录",
    email: "邮箱",
    password: "密码",
    logout: "退出登录",
    questionCount: "{count} 题",
    score: "{score} 分",
    duration: "{minutes} 分钟",
    startPractice: "开始练习",
    startExam: "开始考试",
    practiceMode: "练习模式",
    examMode: "考试模式",
    elapsed: "已用时间",
    remaining: "剩余时间",
    prev: "上一题",
    next: "下一题",
    submit: "提交",
    submitPaper: "交卷",
    finish: "结束练习",
    answered: "已答",
    wrong: "错误",
    unanswered: "未答",
    flagged: "标记",
    correct: "答对了",
    incorrect: "答错了",
    rationale: "解析",
    referenceAnswer: "参考答案",
    iWasRight: "我答对了",
    iWasWrong: "我答错了",
    tabWrongTitle: "我的错题",
    tabBookmarked: "我的收藏",
    tabFlagged: "我的纠错",
    rePractice: "重新练习",
    markMastered: "我已掌握",
    mastered: "已掌握",
    wrongNTimes: "错误 {count} 次",
    viewAnswer: "查看解析",
    empty: "这里还是空的",
    reportTitle: "考试报告",
    passed: "通过",
    failed: "未通过",
    interfaceLanguage: "界面语言",
    contentLanguage: "题目语言",
    changePassword: "修改密码",
    settings: "设置",
    loading: "加载中...",
  },
};

let currentLocale = null;

function init() {
  const saved = storage.getItem(storage.KEYS.LOCALE);
  currentLocale = saved === "en" || saved === "zh" ? saved : "zh";
  return currentLocale;
}

function getLocale() {
  if (!currentLocale) init();
  return currentLocale;
}

function setLocale(locale) {
  if (DICTS[locale]) {
    currentLocale = locale;
    storage.setItem(storage.KEYS.LOCALE, locale);
  }
}

/** t("wrongNTimes", { count: 3 }) -> "Wrong 3x" / "错误 3 次" */
function t(key, vars) {
  if (!currentLocale) init();
  let text = DICTS[currentLocale][key] ?? DICTS.en[key] ?? key;
  if (vars) {
    Object.entries(vars).forEach(([k, v]) => {
      text = text.split(`{${k}}`).join(String(v));
    });
  }
  return text;
}

module.exports = { t, init, getLocale, setLocale, DICTS };
