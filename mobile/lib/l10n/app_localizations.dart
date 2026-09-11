import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('zh'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'CISSP Compass'**
  String get appTitle;

  /// No description provided for @brandName.
  ///
  /// In en, this message translates to:
  /// **'CISSP Compass'**
  String get brandName;

  /// No description provided for @brandTagline.
  ///
  /// In en, this message translates to:
  /// **'Master cybersecurity certification'**
  String get brandTagline;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navPractice.
  ///
  /// In en, this message translates to:
  /// **'Practice'**
  String get navPractice;

  /// No description provided for @navReview.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get navReview;

  /// No description provided for @navExam.
  ///
  /// In en, this message translates to:
  /// **'Exam'**
  String get navExam;

  /// No description provided for @navAnalytics.
  ///
  /// In en, this message translates to:
  /// **'Analytics'**
  String get navAnalytics;

  /// No description provided for @navSettings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get navSettings;

  /// No description provided for @navLogout.
  ///
  /// In en, this message translates to:
  /// **'Log out'**
  String get navLogout;

  /// No description provided for @commonSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get commonSave;

  /// No description provided for @commonCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get commonCancel;

  /// No description provided for @commonSubmit.
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get commonSubmit;

  /// No description provided for @commonRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get commonRetry;

  /// No description provided for @commonLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get commonLoading;

  /// No description provided for @commonPrevious.
  ///
  /// In en, this message translates to:
  /// **'Previous'**
  String get commonPrevious;

  /// No description provided for @commonNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get commonNext;

  /// No description provided for @commonOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get commonOpen;

  /// No description provided for @commonErrorTitle.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong'**
  String get commonErrorTitle;

  /// No description provided for @commonContinue.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get commonContinue;

  /// No description provided for @commonOfN.
  ///
  /// In en, this message translates to:
  /// **'of {n}'**
  String commonOfN(int n);

  /// No description provided for @langEn.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get langEn;

  /// No description provided for @langZh.
  ///
  /// In en, this message translates to:
  /// **'中文'**
  String get langZh;

  /// No description provided for @langBilingual.
  ///
  /// In en, this message translates to:
  /// **'Both'**
  String get langBilingual;

  /// No description provided for @authLogin.
  ///
  /// In en, this message translates to:
  /// **'Log in'**
  String get authLogin;

  /// No description provided for @authLoggingIn.
  ///
  /// In en, this message translates to:
  /// **'Logging in…'**
  String get authLoggingIn;

  /// No description provided for @authRegister.
  ///
  /// In en, this message translates to:
  /// **'Register'**
  String get authRegister;

  /// No description provided for @authEmail.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get authEmail;

  /// No description provided for @authPassword.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get authPassword;

  /// No description provided for @authDisplayName.
  ///
  /// In en, this message translates to:
  /// **'Display name'**
  String get authDisplayName;

  /// No description provided for @authOptional.
  ///
  /// In en, this message translates to:
  /// **'Optional'**
  String get authOptional;

  /// No description provided for @authPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Min 8 characters'**
  String get authPasswordHint;

  /// No description provided for @authEmailPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'you@example.com'**
  String get authEmailPlaceholder;

  /// No description provided for @authPasswordPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get authPasswordPlaceholder;

  /// No description provided for @authNoAccount.
  ///
  /// In en, this message translates to:
  /// **'No account?'**
  String get authNoAccount;

  /// No description provided for @authHaveAccount.
  ///
  /// In en, this message translates to:
  /// **'Already have an account?'**
  String get authHaveAccount;

  /// No description provided for @authDevLogin.
  ///
  /// In en, this message translates to:
  /// **'Dev login (admin)'**
  String get authDevLogin;

  /// No description provided for @authTooManyAttempts.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Try later.'**
  String get authTooManyAttempts;

  /// No description provided for @authInvalidCredentials.
  ///
  /// In en, this message translates to:
  /// **'Invalid credentials.'**
  String get authInvalidCredentials;

  /// No description provided for @authEmailExists.
  ///
  /// In en, this message translates to:
  /// **'Email already registered.'**
  String get authEmailExists;

  /// No description provided for @authNetworkError.
  ///
  /// In en, this message translates to:
  /// **'Could not reach the server. Check your connection and try again.'**
  String get authNetworkError;

  /// No description provided for @authRegisterFailed.
  ///
  /// In en, this message translates to:
  /// **'Registration failed. Please try again.'**
  String get authRegisterFailed;

  /// No description provided for @authForgotPassword.
  ///
  /// In en, this message translates to:
  /// **'Forgot password?'**
  String get authForgotPassword;

  /// No description provided for @authForgotPasswordTitle.
  ///
  /// In en, this message translates to:
  /// **'Reset password'**
  String get authForgotPasswordTitle;

  /// No description provided for @authForgotPasswordDesc.
  ///
  /// In en, this message translates to:
  /// **'Enter your email to request a reset token.'**
  String get authForgotPasswordDesc;

  /// No description provided for @authSendResetLink.
  ///
  /// In en, this message translates to:
  /// **'Send reset token'**
  String get authSendResetLink;

  /// No description provided for @authSending.
  ///
  /// In en, this message translates to:
  /// **'Sending…'**
  String get authSending;

  /// No description provided for @authResetToken.
  ///
  /// In en, this message translates to:
  /// **'Reset token'**
  String get authResetToken;

  /// No description provided for @authResetTokenPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Paste the reset token'**
  String get authResetTokenPlaceholder;

  /// No description provided for @authNewPassword.
  ///
  /// In en, this message translates to:
  /// **'New password'**
  String get authNewPassword;

  /// No description provided for @authConfirmReset.
  ///
  /// In en, this message translates to:
  /// **'Reset password'**
  String get authConfirmReset;

  /// No description provided for @authResetting.
  ///
  /// In en, this message translates to:
  /// **'Resetting…'**
  String get authResetting;

  /// No description provided for @authResetSent.
  ///
  /// In en, this message translates to:
  /// **'If that account exists, a reset token was issued.'**
  String get authResetSent;

  /// No description provided for @authPasswordReset.
  ///
  /// In en, this message translates to:
  /// **'Password reset. You can log in now.'**
  String get authPasswordReset;

  /// No description provided for @authResetFailed.
  ///
  /// In en, this message translates to:
  /// **'Reset failed. The token may be invalid or expired.'**
  String get authResetFailed;

  /// No description provided for @authBackToLogin.
  ///
  /// In en, this message translates to:
  /// **'Back to log in'**
  String get authBackToLogin;

  /// No description provided for @authConfirmPassword.
  ///
  /// In en, this message translates to:
  /// **'Confirm password'**
  String get authConfirmPassword;

  /// No description provided for @legalTrademark.
  ///
  /// In en, this message translates to:
  /// **'CISSP® and ISC2® are registered trademarks of ISC2, Inc.'**
  String get legalTrademark;

  /// No description provided for @legalNotOfficial.
  ///
  /// In en, this message translates to:
  /// **'This product is an independent study tool and is not an official ISC2 exam platform, nor is it affiliated with or endorsed by ISC2.'**
  String get legalNotOfficial;

  /// No description provided for @dashboardEyebrow.
  ///
  /// In en, this message translates to:
  /// **'Overview'**
  String get dashboardEyebrow;

  /// No description provided for @dashboardTitle.
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboardTitle;

  /// No description provided for @dashboardDescription.
  ///
  /// In en, this message translates to:
  /// **'Your CISSP study overview at a glance.'**
  String get dashboardDescription;

  /// No description provided for @dashboardContinuePractice.
  ///
  /// In en, this message translates to:
  /// **'Continue practice'**
  String get dashboardContinuePractice;

  /// No description provided for @dashboardNoActivity.
  ///
  /// In en, this message translates to:
  /// **'No activity yet'**
  String get dashboardNoActivity;

  /// No description provided for @dashboardNoActivityDesc.
  ///
  /// In en, this message translates to:
  /// **'Start a practice session to see your accuracy, weak domains, and a tailored review plan here.'**
  String get dashboardNoActivityDesc;

  /// No description provided for @dashboardStartPracticing.
  ///
  /// In en, this message translates to:
  /// **'Start practicing'**
  String get dashboardStartPracticing;

  /// No description provided for @dashboardAccuracy.
  ///
  /// In en, this message translates to:
  /// **'Accuracy'**
  String get dashboardAccuracy;

  /// No description provided for @dashboardAnswered.
  ///
  /// In en, this message translates to:
  /// **'Answered'**
  String get dashboardAnswered;

  /// No description provided for @dashboardStudyTime.
  ///
  /// In en, this message translates to:
  /// **'Study time'**
  String get dashboardStudyTime;

  /// No description provided for @dashboardStreak.
  ///
  /// In en, this message translates to:
  /// **'Streak'**
  String get dashboardStreak;

  /// No description provided for @dashboardStreakDays.
  ///
  /// In en, this message translates to:
  /// **'{n}d'**
  String dashboardStreakDays(int n);

  /// No description provided for @dashboardCorrectOf.
  ///
  /// In en, this message translates to:
  /// **'{c}/{a} correct'**
  String dashboardCorrectOf(int c, int a);

  /// No description provided for @dashboardPracticeTitle.
  ///
  /// In en, this message translates to:
  /// **'Practice'**
  String get dashboardPracticeTitle;

  /// No description provided for @dashboardPracticeDesc.
  ///
  /// In en, this message translates to:
  /// **'Build mastery with scoped sessions across domains and knowledge points.'**
  String get dashboardPracticeDesc;

  /// No description provided for @dashboardMockExamTitle.
  ///
  /// In en, this message translates to:
  /// **'Mock exam'**
  String get dashboardMockExamTitle;

  /// No description provided for @dashboardMockExamDesc.
  ///
  /// In en, this message translates to:
  /// **'Train your exam pace with fixed-length and adaptive (CAT) mock exams.'**
  String get dashboardMockExamDesc;

  /// No description provided for @dashboardStartExamCta.
  ///
  /// In en, this message translates to:
  /// **'Start an exam'**
  String get dashboardStartExamCta;

  /// No description provided for @dashboardReviewTitle.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get dashboardReviewTitle;

  /// No description provided for @dashboardReviewDesc.
  ///
  /// In en, this message translates to:
  /// **'Re-practice wrong, bookmarked, and flagged questions to close the gaps.'**
  String get dashboardReviewDesc;

  /// No description provided for @dashboardReviewCta.
  ///
  /// In en, this message translates to:
  /// **'Review errors'**
  String get dashboardReviewCta;

  /// No description provided for @dashboardWeakDomains.
  ///
  /// In en, this message translates to:
  /// **'Weak domains'**
  String get dashboardWeakDomains;

  /// No description provided for @dashboardDomainMastery.
  ///
  /// In en, this message translates to:
  /// **'Domain mastery'**
  String get dashboardDomainMastery;

  /// No description provided for @dashboardLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading your dashboard…'**
  String get dashboardLoading;

  /// No description provided for @dashboardLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load your dashboard.'**
  String get dashboardLoadFailed;

  /// No description provided for @dashboardTodayRec.
  ///
  /// In en, this message translates to:
  /// **'Today\'s recommendation'**
  String get dashboardTodayRec;

  /// No description provided for @analyticsEyebrow.
  ///
  /// In en, this message translates to:
  /// **'Insights'**
  String get analyticsEyebrow;

  /// No description provided for @analyticsTitle.
  ///
  /// In en, this message translates to:
  /// **'Analytics'**
  String get analyticsTitle;

  /// No description provided for @analyticsDescription.
  ///
  /// In en, this message translates to:
  /// **'Detailed breakdown of your performance over time.'**
  String get analyticsDescription;

  /// No description provided for @analyticsPerformance.
  ///
  /// In en, this message translates to:
  /// **'Performance'**
  String get analyticsPerformance;

  /// No description provided for @analyticsAccuracyTrend.
  ///
  /// In en, this message translates to:
  /// **'Accuracy trend'**
  String get analyticsAccuracyTrend;

  /// No description provided for @analyticsMastery.
  ///
  /// In en, this message translates to:
  /// **'Mastery'**
  String get analyticsMastery;

  /// No description provided for @analyticsDomainMastery.
  ///
  /// In en, this message translates to:
  /// **'Domain mastery'**
  String get analyticsDomainMastery;

  /// No description provided for @analyticsFocusAreas.
  ///
  /// In en, this message translates to:
  /// **'Focus areas'**
  String get analyticsFocusAreas;

  /// No description provided for @analyticsWeakKp.
  ///
  /// In en, this message translates to:
  /// **'Weak knowledge points'**
  String get analyticsWeakKp;

  /// No description provided for @analyticsErrorTypes.
  ///
  /// In en, this message translates to:
  /// **'Error types'**
  String get analyticsErrorTypes;

  /// No description provided for @analyticsLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading analytics…'**
  String get analyticsLoading;

  /// No description provided for @analyticsLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load analytics.'**
  String get analyticsLoadFailed;

  /// No description provided for @analyticsColDomain.
  ///
  /// In en, this message translates to:
  /// **'Domain'**
  String get analyticsColDomain;

  /// No description provided for @analyticsColAccuracy.
  ///
  /// In en, this message translates to:
  /// **'Accuracy'**
  String get analyticsColAccuracy;

  /// No description provided for @analyticsColAnswered.
  ///
  /// In en, this message translates to:
  /// **'Answered'**
  String get analyticsColAnswered;

  /// No description provided for @practiceTitle.
  ///
  /// In en, this message translates to:
  /// **'Practice'**
  String get practiceTitle;

  /// No description provided for @practiceDescription.
  ///
  /// In en, this message translates to:
  /// **'Build and resume scoped practice sessions.'**
  String get practiceDescription;

  /// No description provided for @practiceNewSession.
  ///
  /// In en, this message translates to:
  /// **'New session'**
  String get practiceNewSession;

  /// No description provided for @practiceResume.
  ///
  /// In en, this message translates to:
  /// **'Resume'**
  String get practiceResume;

  /// No description provided for @practiceStart.
  ///
  /// In en, this message translates to:
  /// **'Start practice'**
  String get practiceStart;

  /// No description provided for @practiceSubmit.
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get practiceSubmit;

  /// No description provided for @practiceNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get practiceNext;

  /// No description provided for @practiceFinish.
  ///
  /// In en, this message translates to:
  /// **'Finish'**
  String get practiceFinish;

  /// No description provided for @practicePause.
  ///
  /// In en, this message translates to:
  /// **'Pause'**
  String get practicePause;

  /// No description provided for @practiceResumeAction.
  ///
  /// In en, this message translates to:
  /// **'Resume session'**
  String get practiceResumeAction;

  /// No description provided for @practiceSessionPaused.
  ///
  /// In en, this message translates to:
  /// **'Session paused. Resume to continue.'**
  String get practiceSessionPaused;

  /// No description provided for @practiceCorrect.
  ///
  /// In en, this message translates to:
  /// **'Correct'**
  String get practiceCorrect;

  /// No description provided for @practiceIncorrect.
  ///
  /// In en, this message translates to:
  /// **'Incorrect'**
  String get practiceIncorrect;

  /// No description provided for @practiceSummaryTitle.
  ///
  /// In en, this message translates to:
  /// **'Practice summary'**
  String get practiceSummaryTitle;

  /// No description provided for @practiceLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get practiceLoading;

  /// No description provided for @practiceCouldNotStart.
  ///
  /// In en, this message translates to:
  /// **'Could not start the session.'**
  String get practiceCouldNotStart;

  /// No description provided for @practiceAlreadyAnswered.
  ///
  /// In en, this message translates to:
  /// **'Already answered.'**
  String get practiceAlreadyAnswered;

  /// No description provided for @practiceCount.
  ///
  /// In en, this message translates to:
  /// **'Question count'**
  String get practiceCount;

  /// No description provided for @practiceSubset.
  ///
  /// In en, this message translates to:
  /// **'Subset'**
  String get practiceSubset;

  /// No description provided for @practiceOrder.
  ///
  /// In en, this message translates to:
  /// **'Order'**
  String get practiceOrder;

  /// No description provided for @practiceDomain.
  ///
  /// In en, this message translates to:
  /// **'Domain'**
  String get practiceDomain;

  /// No description provided for @practiceAnyDomain.
  ///
  /// In en, this message translates to:
  /// **'Any domain'**
  String get practiceAnyDomain;

  /// No description provided for @practiceBook.
  ///
  /// In en, this message translates to:
  /// **'Book'**
  String get practiceBook;

  /// No description provided for @practiceAnyBook.
  ///
  /// In en, this message translates to:
  /// **'Any book'**
  String get practiceAnyBook;

  /// No description provided for @practiceChapter.
  ///
  /// In en, this message translates to:
  /// **'Chapter'**
  String get practiceChapter;

  /// No description provided for @practiceAnyChapter.
  ///
  /// In en, this message translates to:
  /// **'Any chapter'**
  String get practiceAnyChapter;

  /// No description provided for @practiceKeyPoints.
  ///
  /// In en, this message translates to:
  /// **'Key points'**
  String get practiceKeyPoints;

  /// No description provided for @practiceOptionExplanations.
  ///
  /// In en, this message translates to:
  /// **'Option explanations'**
  String get practiceOptionExplanations;

  /// No description provided for @practiceLanguage.
  ///
  /// In en, this message translates to:
  /// **'Question language'**
  String get practiceLanguage;

  /// No description provided for @practiceShuffleOptions.
  ///
  /// In en, this message translates to:
  /// **'Shuffle options'**
  String get practiceShuffleOptions;

  /// No description provided for @practiceActiveSessions.
  ///
  /// In en, this message translates to:
  /// **'Active sessions'**
  String get practiceActiveSessions;

  /// No description provided for @practiceBookmark.
  ///
  /// In en, this message translates to:
  /// **'Bookmark'**
  String get practiceBookmark;

  /// No description provided for @practiceFlag.
  ///
  /// In en, this message translates to:
  /// **'Flag for review'**
  String get practiceFlag;

  /// No description provided for @practiceMastered.
  ///
  /// In en, this message translates to:
  /// **'Mastered'**
  String get practiceMastered;

  /// No description provided for @practiceQuestioned.
  ///
  /// In en, this message translates to:
  /// **'Have a question'**
  String get practiceQuestioned;

  /// No description provided for @practiceMapping.
  ///
  /// In en, this message translates to:
  /// **'Topic mapping'**
  String get practiceMapping;

  /// No description provided for @practiceHistory.
  ///
  /// In en, this message translates to:
  /// **'Past attempts'**
  String get practiceHistory;

  /// No description provided for @practiceRelated.
  ///
  /// In en, this message translates to:
  /// **'Related questions'**
  String get practiceRelated;

  /// No description provided for @practiceHistoryCorrect.
  ///
  /// In en, this message translates to:
  /// **'Correct'**
  String get practiceHistoryCorrect;

  /// No description provided for @practiceHistoryIncorrect.
  ///
  /// In en, this message translates to:
  /// **'Incorrect'**
  String get practiceHistoryIncorrect;

  /// No description provided for @practiceDifficulty.
  ///
  /// In en, this message translates to:
  /// **'Difficulty'**
  String get practiceDifficulty;

  /// No description provided for @practiceAnyDifficulty.
  ///
  /// In en, this message translates to:
  /// **'Any difficulty'**
  String get practiceAnyDifficulty;

  /// No description provided for @practiceQuestionType.
  ///
  /// In en, this message translates to:
  /// **'Question type'**
  String get practiceQuestionType;

  /// No description provided for @practiceAnyQuestionType.
  ///
  /// In en, this message translates to:
  /// **'Any type'**
  String get practiceAnyQuestionType;

  /// No description provided for @practiceTag.
  ///
  /// In en, this message translates to:
  /// **'Tag'**
  String get practiceTag;

  /// No description provided for @practiceAnyTag.
  ///
  /// In en, this message translates to:
  /// **'Any tag'**
  String get practiceAnyTag;

  /// No description provided for @questionTypeSingle.
  ///
  /// In en, this message translates to:
  /// **'Single choice'**
  String get questionTypeSingle;

  /// No description provided for @questionTypeMultiple.
  ///
  /// In en, this message translates to:
  /// **'Multiple choice'**
  String get questionTypeMultiple;

  /// No description provided for @questionTypeTrueFalse.
  ///
  /// In en, this message translates to:
  /// **'True / false'**
  String get questionTypeTrueFalse;

  /// No description provided for @practiceNote.
  ///
  /// In en, this message translates to:
  /// **'Note'**
  String get practiceNote;

  /// No description provided for @practiceErrorType.
  ///
  /// In en, this message translates to:
  /// **'Error type'**
  String get practiceErrorType;

  /// No description provided for @practiceAnother.
  ///
  /// In en, this message translates to:
  /// **'Another set'**
  String get practiceAnother;

  /// No description provided for @practiceBackHome.
  ///
  /// In en, this message translates to:
  /// **'Back to practice'**
  String get practiceBackHome;

  /// No description provided for @practiceAccuracy.
  ///
  /// In en, this message translates to:
  /// **'Accuracy'**
  String get practiceAccuracy;

  /// No description provided for @practiceTimeSpent.
  ///
  /// In en, this message translates to:
  /// **'Time spent'**
  String get practiceTimeSpent;

  /// No description provided for @practiceDomains.
  ///
  /// In en, this message translates to:
  /// **'By domain'**
  String get practiceDomains;

  /// No description provided for @practiceWrongList.
  ///
  /// In en, this message translates to:
  /// **'Wrong questions'**
  String get practiceWrongList;

  /// No description provided for @practiceQuestionOf.
  ///
  /// In en, this message translates to:
  /// **'Question {current} of {total}'**
  String practiceQuestionOf(int current, int total);

  /// No description provided for @subsetAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get subsetAll;

  /// No description provided for @subsetUnpracticed.
  ///
  /// In en, this message translates to:
  /// **'Unpracticed'**
  String get subsetUnpracticed;

  /// No description provided for @subsetWrong.
  ///
  /// In en, this message translates to:
  /// **'Wrong'**
  String get subsetWrong;

  /// No description provided for @subsetBookmarked.
  ///
  /// In en, this message translates to:
  /// **'Bookmarked'**
  String get subsetBookmarked;

  /// No description provided for @subsetNeedsReview.
  ///
  /// In en, this message translates to:
  /// **'Needs review'**
  String get subsetNeedsReview;

  /// No description provided for @orderRandom.
  ///
  /// In en, this message translates to:
  /// **'Random'**
  String get orderRandom;

  /// No description provided for @orderSequential.
  ///
  /// In en, this message translates to:
  /// **'Sequential'**
  String get orderSequential;

  /// No description provided for @orderEasyToHard.
  ///
  /// In en, this message translates to:
  /// **'Easy to hard'**
  String get orderEasyToHard;

  /// No description provided for @orderWeakFirst.
  ///
  /// In en, this message translates to:
  /// **'Weak first'**
  String get orderWeakFirst;

  /// No description provided for @errorConceptUnclear.
  ///
  /// In en, this message translates to:
  /// **'Concept unclear'**
  String get errorConceptUnclear;

  /// No description provided for @errorMisreadStem.
  ///
  /// In en, this message translates to:
  /// **'Misread stem'**
  String get errorMisreadStem;

  /// No description provided for @errorMemoryLapse.
  ///
  /// In en, this message translates to:
  /// **'Memory lapse'**
  String get errorMemoryLapse;

  /// No description provided for @errorOptionConfusion.
  ///
  /// In en, this message translates to:
  /// **'Option confusion'**
  String get errorOptionConfusion;

  /// No description provided for @errorTimePressure.
  ///
  /// In en, this message translates to:
  /// **'Time pressure'**
  String get errorTimePressure;

  /// No description provided for @reviewTitle.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get reviewTitle;

  /// No description provided for @reviewDescription.
  ///
  /// In en, this message translates to:
  /// **'Re-practice wrong, bookmarked, and flagged questions.'**
  String get reviewDescription;

  /// No description provided for @reviewWrong.
  ///
  /// In en, this message translates to:
  /// **'Wrong questions'**
  String get reviewWrong;

  /// No description provided for @reviewBookmarked.
  ///
  /// In en, this message translates to:
  /// **'Bookmarked'**
  String get reviewBookmarked;

  /// No description provided for @reviewFlagged.
  ///
  /// In en, this message translates to:
  /// **'Needs review'**
  String get reviewFlagged;

  /// No description provided for @reviewWrongDesc.
  ///
  /// In en, this message translates to:
  /// **'Re-practice questions you got wrong.'**
  String get reviewWrongDesc;

  /// No description provided for @reviewBookmarkedDesc.
  ///
  /// In en, this message translates to:
  /// **'Re-practice bookmarked questions.'**
  String get reviewBookmarkedDesc;

  /// No description provided for @reviewFlaggedDesc.
  ///
  /// In en, this message translates to:
  /// **'Re-practice questions flagged for review.'**
  String get reviewFlaggedDesc;

  /// No description provided for @reviewStart.
  ///
  /// In en, this message translates to:
  /// **'Start review session'**
  String get reviewStart;

  /// No description provided for @reviewCouldNotStart.
  ///
  /// In en, this message translates to:
  /// **'No matching questions, or could not start.'**
  String get reviewCouldNotStart;

  /// No description provided for @examTitle.
  ///
  /// In en, this message translates to:
  /// **'Mock exams'**
  String get examTitle;

  /// No description provided for @examDescription.
  ///
  /// In en, this message translates to:
  /// **'Train your exam pace with fixed-length and adaptive (CAT) mock exams.'**
  String get examDescription;

  /// No description provided for @examNew.
  ///
  /// In en, this message translates to:
  /// **'New exam'**
  String get examNew;

  /// No description provided for @examHistory.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get examHistory;

  /// No description provided for @examFixedTitle.
  ///
  /// In en, this message translates to:
  /// **'Fixed mock exam'**
  String get examFixedTitle;

  /// No description provided for @examCatTitle.
  ///
  /// In en, this message translates to:
  /// **'CAT mock exam'**
  String get examCatTitle;

  /// No description provided for @examStartFixed.
  ///
  /// In en, this message translates to:
  /// **'Start fixed exam'**
  String get examStartFixed;

  /// No description provided for @examStartCat.
  ///
  /// In en, this message translates to:
  /// **'Start CAT exam'**
  String get examStartCat;

  /// No description provided for @examReportTitle.
  ///
  /// In en, this message translates to:
  /// **'Exam report'**
  String get examReportTitle;

  /// No description provided for @examReviewTitle.
  ///
  /// In en, this message translates to:
  /// **'Answer review'**
  String get examReviewTitle;

  /// No description provided for @examFinish.
  ///
  /// In en, this message translates to:
  /// **'Finish exam'**
  String get examFinish;

  /// No description provided for @examTimeRemaining.
  ///
  /// In en, this message translates to:
  /// **'Time remaining'**
  String get examTimeRemaining;

  /// No description provided for @examPass.
  ///
  /// In en, this message translates to:
  /// **'PASS'**
  String get examPass;

  /// No description provided for @examFail.
  ///
  /// In en, this message translates to:
  /// **'FAIL'**
  String get examFail;

  /// No description provided for @examLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading exam…'**
  String get examLoading;

  /// No description provided for @examCatDisclaimer.
  ///
  /// In en, this message translates to:
  /// **'Study tool — not an official ISC2 score. Forward-only; answers cannot be revised.'**
  String get examCatDisclaimer;

  /// No description provided for @examAcknowledgeFixed.
  ///
  /// In en, this message translates to:
  /// **'I understand this is a timed mock exam.'**
  String get examAcknowledgeFixed;

  /// No description provided for @examAcknowledgeCat.
  ///
  /// In en, this message translates to:
  /// **'I understand CAT is forward-only and answers cannot be revised.'**
  String get examAcknowledgeCat;

  /// No description provided for @examResume.
  ///
  /// In en, this message translates to:
  /// **'Resume exam'**
  String get examResume;

  /// No description provided for @examActiveSessions.
  ///
  /// In en, this message translates to:
  /// **'In progress'**
  String get examActiveSessions;

  /// No description provided for @examScore.
  ///
  /// In en, this message translates to:
  /// **'Score'**
  String get examScore;

  /// No description provided for @examAccuracy.
  ///
  /// In en, this message translates to:
  /// **'Accuracy'**
  String get examAccuracy;

  /// No description provided for @examAbility.
  ///
  /// In en, this message translates to:
  /// **'Ability estimate'**
  String get examAbility;

  /// No description provided for @examSem.
  ///
  /// In en, this message translates to:
  /// **'SEM'**
  String get examSem;

  /// No description provided for @examReadiness.
  ///
  /// In en, this message translates to:
  /// **'Readiness'**
  String get examReadiness;

  /// No description provided for @examYourAnswer.
  ///
  /// In en, this message translates to:
  /// **'Your answer'**
  String get examYourAnswer;

  /// No description provided for @examCorrectAnswer.
  ///
  /// In en, this message translates to:
  /// **'Correct'**
  String get examCorrectAnswer;

  /// No description provided for @examTimeUp.
  ///
  /// In en, this message translates to:
  /// **'Time is up — submitting.'**
  String get examTimeUp;

  /// No description provided for @examNotInProgress.
  ///
  /// In en, this message translates to:
  /// **'Exam is no longer in progress.'**
  String get examNotInProgress;

  /// No description provided for @examCouldNotStart.
  ///
  /// In en, this message translates to:
  /// **'Could not start the exam.'**
  String get examCouldNotStart;

  /// No description provided for @examViewReview.
  ///
  /// In en, this message translates to:
  /// **'Review answers'**
  String get examViewReview;

  /// No description provided for @examBackHome.
  ///
  /// In en, this message translates to:
  /// **'Back to exams'**
  String get examBackHome;

  /// No description provided for @examQuestionOf.
  ///
  /// In en, this message translates to:
  /// **'Question {current} of {total}'**
  String examQuestionOf(int current, int total);

  /// No description provided for @settingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settingsTitle;

  /// No description provided for @settingsDescription.
  ///
  /// In en, this message translates to:
  /// **'Manage your language and content preferences.'**
  String get settingsDescription;

  /// No description provided for @settingsInterfaceTitle.
  ///
  /// In en, this message translates to:
  /// **'Interface language'**
  String get settingsInterfaceTitle;

  /// No description provided for @settingsInterfaceDesc.
  ///
  /// In en, this message translates to:
  /// **'Choose the language for menus, buttons, and labels.'**
  String get settingsInterfaceDesc;

  /// No description provided for @settingsContentTitle.
  ///
  /// In en, this message translates to:
  /// **'Question content language'**
  String get settingsContentTitle;

  /// No description provided for @settingsContentDesc.
  ///
  /// In en, this message translates to:
  /// **'Choose how questions are displayed.'**
  String get settingsContentDesc;

  /// No description provided for @settingsSaved.
  ///
  /// In en, this message translates to:
  /// **'Saved.'**
  String get settingsSaved;

  /// No description provided for @settingsChangePasswordTitle.
  ///
  /// In en, this message translates to:
  /// **'Change password'**
  String get settingsChangePasswordTitle;

  /// No description provided for @settingsChangePasswordDesc.
  ///
  /// In en, this message translates to:
  /// **'Update your account password.'**
  String get settingsChangePasswordDesc;

  /// No description provided for @settingsCurrentPassword.
  ///
  /// In en, this message translates to:
  /// **'Current password'**
  String get settingsCurrentPassword;

  /// No description provided for @settingsNewPassword.
  ///
  /// In en, this message translates to:
  /// **'New password'**
  String get settingsNewPassword;

  /// No description provided for @settingsConfirmPassword.
  ///
  /// In en, this message translates to:
  /// **'Confirm new password'**
  String get settingsConfirmPassword;

  /// No description provided for @settingsPasswordChanged.
  ///
  /// In en, this message translates to:
  /// **'Password changed.'**
  String get settingsPasswordChanged;

  /// No description provided for @settingsPasswordMismatch.
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match.'**
  String get settingsPasswordMismatch;

  /// No description provided for @settingsPasswordIncorrect.
  ///
  /// In en, this message translates to:
  /// **'Current password is incorrect.'**
  String get settingsPasswordIncorrect;

  /// No description provided for @settingsUpdating.
  ///
  /// In en, this message translates to:
  /// **'Updating…'**
  String get settingsUpdating;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
