// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'CISSP Compass';

  @override
  String get brandName => 'CISSP Compass';

  @override
  String get brandTagline => 'Master cybersecurity certification';

  @override
  String get navHome => 'Home';

  @override
  String get navPractice => 'Practice';

  @override
  String get navReview => 'Review';

  @override
  String get navExam => 'Exam';

  @override
  String get navAnalytics => 'Analytics';

  @override
  String get navSettings => 'Settings';

  @override
  String get navLogout => 'Log out';

  @override
  String get commonSave => 'Save';

  @override
  String get commonCancel => 'Cancel';

  @override
  String get commonSubmit => 'Submit';

  @override
  String get commonRetry => 'Retry';

  @override
  String get commonLoading => 'Loading…';

  @override
  String get commonPrevious => 'Previous';

  @override
  String get commonNext => 'Next';

  @override
  String get commonOpen => 'Open';

  @override
  String get commonErrorTitle => 'Something went wrong';

  @override
  String get commonContinue => 'Continue';

  @override
  String commonOfN(int n) {
    return 'of $n';
  }

  @override
  String get langEn => 'English';

  @override
  String get langZh => '中文';

  @override
  String get langBilingual => 'Both';

  @override
  String get authLogin => 'Log in';

  @override
  String get authLoggingIn => 'Logging in…';

  @override
  String get authRegister => 'Register';

  @override
  String get authEmail => 'Email';

  @override
  String get authPassword => 'Password';

  @override
  String get authDisplayName => 'Display name';

  @override
  String get authOptional => 'Optional';

  @override
  String get authPasswordHint => 'Min 8 characters';

  @override
  String get authEmailPlaceholder => 'you@example.com';

  @override
  String get authPasswordPlaceholder => 'Enter your password';

  @override
  String get authNoAccount => 'No account?';

  @override
  String get authHaveAccount => 'Already have an account?';

  @override
  String get authDevLogin => 'Dev login (admin / admin)';

  @override
  String get authTooManyAttempts => 'Too many attempts. Try later.';

  @override
  String get authInvalidCredentials => 'Invalid credentials.';

  @override
  String get authEmailExists => 'Email already registered.';

  @override
  String get authNetworkError =>
      'Could not reach the server. Check your connection and try again.';

  @override
  String get authRegisterFailed => 'Registration failed. Please try again.';

  @override
  String get authForgotPassword => 'Forgot password?';

  @override
  String get authForgotPasswordTitle => 'Reset password';

  @override
  String get authForgotPasswordDesc =>
      'Enter your email to request a reset token.';

  @override
  String get authSendResetLink => 'Send reset token';

  @override
  String get authSending => 'Sending…';

  @override
  String get authResetToken => 'Reset token';

  @override
  String get authResetTokenPlaceholder => 'Paste the reset token';

  @override
  String get authNewPassword => 'New password';

  @override
  String get authConfirmReset => 'Reset password';

  @override
  String get authResetting => 'Resetting…';

  @override
  String get authResetSent =>
      'If that account exists, a reset token was issued.';

  @override
  String get authPasswordReset => 'Password reset. You can log in now.';

  @override
  String get authResetFailed =>
      'Reset failed. The token may be invalid or expired.';

  @override
  String get authBackToLogin => 'Back to log in';

  @override
  String get authConfirmPassword => 'Confirm password';

  @override
  String get legalTrademark =>
      'CISSP® and ISC2® are registered trademarks of ISC2, Inc.';

  @override
  String get legalNotOfficial =>
      'This product is an independent study tool and is not an official ISC2 exam platform, nor is it affiliated with or endorsed by ISC2.';

  @override
  String get dashboardEyebrow => 'Overview';

  @override
  String get dashboardTitle => 'Dashboard';

  @override
  String get dashboardDescription => 'Your CISSP study overview at a glance.';

  @override
  String get dashboardContinuePractice => 'Continue practice';

  @override
  String get dashboardNoActivity => 'No activity yet';

  @override
  String get dashboardNoActivityDesc =>
      'Start a practice session to see your accuracy, weak domains, and a tailored review plan here.';

  @override
  String get dashboardStartPracticing => 'Start practicing';

  @override
  String get dashboardAccuracy => 'Accuracy';

  @override
  String get dashboardAnswered => 'Answered';

  @override
  String get dashboardStudyTime => 'Study time';

  @override
  String get dashboardStreak => 'Streak';

  @override
  String dashboardStreakDays(int n) {
    return '${n}d';
  }

  @override
  String dashboardCorrectOf(int c, int a) {
    return '$c/$a correct';
  }

  @override
  String get dashboardPracticeTitle => 'Practice';

  @override
  String get dashboardPracticeDesc =>
      'Build mastery with scoped sessions across domains and knowledge points.';

  @override
  String get dashboardMockExamTitle => 'Mock exam';

  @override
  String get dashboardMockExamDesc =>
      'Train your exam pace with fixed-length and adaptive (CAT) mock exams.';

  @override
  String get dashboardStartExamCta => 'Start an exam';

  @override
  String get dashboardReviewTitle => 'Review';

  @override
  String get dashboardReviewDesc =>
      'Re-practice wrong, bookmarked, and flagged questions to close the gaps.';

  @override
  String get dashboardReviewCta => 'Review errors';

  @override
  String get dashboardWeakDomains => 'Weak domains';

  @override
  String get dashboardDomainMastery => 'Domain mastery';

  @override
  String get dashboardLoading => 'Loading your dashboard…';

  @override
  String get dashboardLoadFailed => 'Could not load your dashboard.';

  @override
  String get dashboardTodayRec => 'Today\'s recommendation';

  @override
  String get analyticsEyebrow => 'Insights';

  @override
  String get analyticsTitle => 'Analytics';

  @override
  String get analyticsDescription =>
      'Detailed breakdown of your performance over time.';

  @override
  String get analyticsPerformance => 'Performance';

  @override
  String get analyticsAccuracyTrend => 'Accuracy trend';

  @override
  String get analyticsMastery => 'Mastery';

  @override
  String get analyticsDomainMastery => 'Domain mastery';

  @override
  String get analyticsFocusAreas => 'Focus areas';

  @override
  String get analyticsWeakKp => 'Weak knowledge points';

  @override
  String get analyticsErrorTypes => 'Error types';

  @override
  String get analyticsLoading => 'Loading analytics…';

  @override
  String get analyticsLoadFailed => 'Could not load analytics.';

  @override
  String get analyticsColDomain => 'Domain';

  @override
  String get analyticsColAccuracy => 'Accuracy';

  @override
  String get analyticsColAnswered => 'Answered';

  @override
  String get practiceTitle => 'Practice';

  @override
  String get practiceDescription =>
      'Build and resume scoped practice sessions.';

  @override
  String get practiceNewSession => 'New session';

  @override
  String get practiceResume => 'Resume';

  @override
  String get practiceStart => 'Start practice';

  @override
  String get practiceSubmit => 'Submit';

  @override
  String get practiceNext => 'Next';

  @override
  String get practiceFinish => 'Finish';

  @override
  String get practicePause => 'Pause';

  @override
  String get practiceResumeAction => 'Resume session';

  @override
  String get practiceSessionPaused => 'Session paused. Resume to continue.';

  @override
  String get practiceCorrect => 'Correct';

  @override
  String get practiceIncorrect => 'Incorrect';

  @override
  String get practiceSummaryTitle => 'Practice summary';

  @override
  String get practiceLoading => 'Loading…';

  @override
  String get practiceCouldNotStart => 'Could not start the session.';

  @override
  String get practiceAlreadyAnswered => 'Already answered.';

  @override
  String get practiceCount => 'Question count';

  @override
  String get practiceSubset => 'Subset';

  @override
  String get practiceOrder => 'Order';

  @override
  String get practiceDomain => 'Domain';

  @override
  String get practiceAnyDomain => 'Any domain';

  @override
  String get practiceBook => 'Book';

  @override
  String get practiceAnyBook => 'Any book';

  @override
  String get practiceChapter => 'Chapter';

  @override
  String get practiceAnyChapter => 'Any chapter';

  @override
  String get practiceKeyPoints => 'Key points';

  @override
  String get practiceOptionExplanations => 'Option explanations';

  @override
  String get practiceLanguage => 'Question language';

  @override
  String get practiceShuffleOptions => 'Shuffle options';

  @override
  String get practiceActiveSessions => 'Active sessions';

  @override
  String get practiceBookmark => 'Bookmark';

  @override
  String get practiceFlag => 'Flag for review';

  @override
  String get practiceMastered => 'Mastered';

  @override
  String get practiceQuestioned => 'Have a question';

  @override
  String get practiceMapping => 'Topic mapping';

  @override
  String get practiceHistory => 'Past attempts';

  @override
  String get practiceRelated => 'Related questions';

  @override
  String get practiceHistoryCorrect => 'Correct';

  @override
  String get practiceHistoryIncorrect => 'Incorrect';

  @override
  String get practiceDifficulty => 'Difficulty';

  @override
  String get practiceAnyDifficulty => 'Any difficulty';

  @override
  String get practiceQuestionType => 'Question type';

  @override
  String get practiceAnyQuestionType => 'Any type';

  @override
  String get practiceTag => 'Tag';

  @override
  String get practiceAnyTag => 'Any tag';

  @override
  String get questionTypeSingle => 'Single choice';

  @override
  String get questionTypeMultiple => 'Multiple choice';

  @override
  String get questionTypeTrueFalse => 'True / false';

  @override
  String get practiceNote => 'Note';

  @override
  String get practiceErrorType => 'Error type';

  @override
  String get practiceAnother => 'Another set';

  @override
  String get practiceBackHome => 'Back to practice';

  @override
  String get practiceAccuracy => 'Accuracy';

  @override
  String get practiceTimeSpent => 'Time spent';

  @override
  String get practiceDomains => 'By domain';

  @override
  String get practiceWrongList => 'Wrong questions';

  @override
  String practiceQuestionOf(int current, int total) {
    return 'Question $current of $total';
  }

  @override
  String get subsetAll => 'All';

  @override
  String get subsetUnpracticed => 'Unpracticed';

  @override
  String get subsetWrong => 'Wrong';

  @override
  String get subsetBookmarked => 'Bookmarked';

  @override
  String get subsetNeedsReview => 'Needs review';

  @override
  String get orderRandom => 'Random';

  @override
  String get orderSequential => 'Sequential';

  @override
  String get orderEasyToHard => 'Easy to hard';

  @override
  String get orderWeakFirst => 'Weak first';

  @override
  String get errorConceptUnclear => 'Concept unclear';

  @override
  String get errorMisreadStem => 'Misread stem';

  @override
  String get errorMemoryLapse => 'Memory lapse';

  @override
  String get errorOptionConfusion => 'Option confusion';

  @override
  String get errorTimePressure => 'Time pressure';

  @override
  String get reviewTitle => 'Review';

  @override
  String get reviewDescription =>
      'Re-practice wrong, bookmarked, and flagged questions.';

  @override
  String get reviewWrong => 'Wrong questions';

  @override
  String get reviewBookmarked => 'Bookmarked';

  @override
  String get reviewFlagged => 'Needs review';

  @override
  String get reviewWrongDesc => 'Re-practice questions you got wrong.';

  @override
  String get reviewBookmarkedDesc => 'Re-practice bookmarked questions.';

  @override
  String get reviewFlaggedDesc => 'Re-practice questions flagged for review.';

  @override
  String get reviewStart => 'Start review session';

  @override
  String get reviewCouldNotStart =>
      'No matching questions, or could not start.';

  @override
  String get examTitle => 'Mock exams';

  @override
  String get examDescription =>
      'Train your exam pace with fixed-length and adaptive (CAT) mock exams.';

  @override
  String get examNew => 'New exam';

  @override
  String get examHistory => 'History';

  @override
  String get examFixedTitle => 'Fixed mock exam';

  @override
  String get examCatTitle => 'CAT mock exam';

  @override
  String get examStartFixed => 'Start fixed exam';

  @override
  String get examStartCat => 'Start CAT exam';

  @override
  String get examReportTitle => 'Exam report';

  @override
  String get examReviewTitle => 'Answer review';

  @override
  String get examFinish => 'Finish exam';

  @override
  String get examTimeRemaining => 'Time remaining';

  @override
  String get examPass => 'PASS';

  @override
  String get examFail => 'FAIL';

  @override
  String get examLoading => 'Loading exam…';

  @override
  String get examCatDisclaimer =>
      'Study tool — not an official ISC2 score. Forward-only; answers cannot be revised.';

  @override
  String get examAcknowledgeFixed => 'I understand this is a timed mock exam.';

  @override
  String get examAcknowledgeCat =>
      'I understand CAT is forward-only and answers cannot be revised.';

  @override
  String get examResume => 'Resume exam';

  @override
  String get examActiveSessions => 'In progress';

  @override
  String get examScore => 'Score';

  @override
  String get examAccuracy => 'Accuracy';

  @override
  String get examAbility => 'Ability estimate';

  @override
  String get examSem => 'SEM';

  @override
  String get examReadiness => 'Readiness';

  @override
  String get examYourAnswer => 'Your answer';

  @override
  String get examCorrectAnswer => 'Correct';

  @override
  String get examTimeUp => 'Time is up — submitting.';

  @override
  String get examNotInProgress => 'Exam is no longer in progress.';

  @override
  String get examCouldNotStart => 'Could not start the exam.';

  @override
  String get examViewReview => 'Review answers';

  @override
  String get examBackHome => 'Back to exams';

  @override
  String examQuestionOf(int current, int total) {
    return 'Question $current of $total';
  }

  @override
  String get settingsTitle => 'Settings';

  @override
  String get settingsDescription =>
      'Manage your language and content preferences.';

  @override
  String get settingsInterfaceTitle => 'Interface language';

  @override
  String get settingsInterfaceDesc =>
      'Choose the language for menus, buttons, and labels.';

  @override
  String get settingsContentTitle => 'Question content language';

  @override
  String get settingsContentDesc => 'Choose how questions are displayed.';

  @override
  String get settingsSaved => 'Saved.';

  @override
  String get settingsChangePasswordTitle => 'Change password';

  @override
  String get settingsChangePasswordDesc => 'Update your account password.';

  @override
  String get settingsCurrentPassword => 'Current password';

  @override
  String get settingsNewPassword => 'New password';

  @override
  String get settingsConfirmPassword => 'Confirm new password';

  @override
  String get settingsPasswordChanged => 'Password changed.';

  @override
  String get settingsPasswordMismatch => 'Passwords do not match.';

  @override
  String get settingsPasswordIncorrect => 'Current password is incorrect.';

  @override
  String get settingsUpdating => 'Updating…';
}
