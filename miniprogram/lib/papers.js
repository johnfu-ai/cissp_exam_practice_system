// Paper + session + wrong-book API surface for the learner flow
// (FR-PAPER/FR-WRONG/FR-ESSAY). Thin wrappers over lib/request.

const { request } = require("./request");

function listPapers() {
  return request("GET", "/api/papers").then((r) => r.data);
}

function getPaper(paperId) {
  return request("GET", `/api/papers/${paperId}`).then((r) => r.data);
}

function createPaperSession(paperId, mode, languageMode) {
  return request("POST", `/api/papers/${paperId}/sessions`, {
    mode,
    ...(languageMode ? { language_mode: languageMode } : {}),
  }).then((r) => r.data);
}

function getPracticeQuestion(sessionId, position) {
  return request("GET", `/api/practice/sessions/${sessionId}/questions/${position}`).then(
    (r) => r.data,
  );
}

function submitPracticeAnswer(sessionId, body) {
  return request("POST", `/api/practice/sessions/${sessionId}/answers`, body).then(
    (r) => r.data,
  );
}

function practiceSelfAssess(sessionId, position, correct) {
  return request(
    "POST",
    `/api/practice/sessions/${sessionId}/questions/${position}/self-assessment`,
    { correct },
  ).then((r) => r.data);
}

function finishPractice(sessionId) {
  return request("POST", `/api/practice/sessions/${sessionId}/finish`).then((r) => r.data);
}

function getExamQuestion(sessionId, position) {
  return request("GET", `/api/exam/sessions/${sessionId}/questions/${position}`).then(
    (r) => r.data,
  );
}

function submitExamAnswer(sessionId, body) {
  return request("POST", `/api/exam/sessions/${sessionId}/answers`, body).then((r) => r.data);
}

function getExamSession(sessionId) {
  return request("GET", `/api/exam/sessions/${sessionId}`).then((r) => r.data);
}

function finishExam(sessionId) {
  return request("POST", `/api/exam/sessions/${sessionId}/finish`).then((r) => r.data);
}

function getExamReport(sessionId) {
  return request("GET", `/api/exam/sessions/${sessionId}/report`).then((r) => r.data);
}

function getExamReview(sessionId) {
  return request("GET", `/api/exam/sessions/${sessionId}/review`).then((r) => r.data);
}

function examSelfAssess(sessionId, position, correct) {
  return request(
    "POST",
    `/api/exam/sessions/${sessionId}/answers/${position}/self-assessment`,
    { correct },
  ).then((r) => r.data);
}

function getWrongBook(tab, paperId) {
  const q = paperId ? `&paper_id=${paperId}` : "";
  return request("GET", `/api/wrong-book?tab=${tab}${q}`).then((r) => r.data);
}

function wrongBookPractice(body) {
  return request("POST", "/api/wrong-book/practice", body).then((r) => r.data);
}

function setQuestionState(questionId, body) {
  return request("PUT", `/api/practice/questions/${questionId}/state`, body).then(
    (r) => r.data,
  );
}

function getPreferences() {
  return request("GET", "/api/users/me/preferences").then((r) => r.data);
}

function changePassword(body) {
  return request("PUT", "/api/auth/password", body).then((r) => r.data);
}

function updatePreferences(body) {
  return request("PUT", "/api/users/me/preferences", body).then((r) => r.data);
}

module.exports = {
  listPapers,
  getPaper,
  createPaperSession,
  getPracticeQuestion,
  submitPracticeAnswer,
  practiceSelfAssess,
  finishPractice,
  getExamQuestion,
  submitExamAnswer,
  getExamSession,
  finishExam,
  getExamReport,
  getExamReview,
  examSelfAssess,
  getWrongBook,
  wrongBookPractice,
  setQuestionState,
  getPreferences,
  updatePreferences,
  changePassword,
};
