// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appTitle => 'CISSP Compass';

  @override
  String get brandName => 'CISSP Compass';

  @override
  String get brandTagline => '掌握网络安全认证';

  @override
  String get navHome => '首页';

  @override
  String get navPractice => '练习';

  @override
  String get navReview => '复习';

  @override
  String get navExam => '模考';

  @override
  String get navAnalytics => '分析';

  @override
  String get navSettings => '设置';

  @override
  String get navLogout => '退出登录';

  @override
  String get commonSave => '保存';

  @override
  String get commonCancel => '取消';

  @override
  String get commonSubmit => '提交';

  @override
  String get commonRetry => '重试';

  @override
  String get commonLoading => '加载中…';

  @override
  String get commonPrevious => '上一题';

  @override
  String get commonNext => '下一题';

  @override
  String get commonOpen => '打开';

  @override
  String get commonErrorTitle => '出错了';

  @override
  String get commonContinue => '继续';

  @override
  String commonOfN(int n) {
    return '共 $n';
  }

  @override
  String get langEn => 'English';

  @override
  String get langZh => '中文';

  @override
  String get langBilingual => '双语';

  @override
  String get authLogin => '登录';

  @override
  String get authLoggingIn => '登录中…';

  @override
  String get authRegister => '注册';

  @override
  String get authEmail => '邮箱';

  @override
  String get authPassword => '密码';

  @override
  String get authDisplayName => '显示名称';

  @override
  String get authOptional => '可选';

  @override
  String get authPasswordHint => '至少 8 个字符';

  @override
  String get authEmailPlaceholder => 'you@example.com';

  @override
  String get authPasswordPlaceholder => '输入密码';

  @override
  String get authNoAccount => '没有账号？';

  @override
  String get authHaveAccount => '已有账号？';

  @override
  String get authDevLogin => '开发登录（admin）';

  @override
  String get authTooManyAttempts => '尝试次数过多，请稍后再试。';

  @override
  String get authInvalidCredentials => '邮箱或密码错误。';

  @override
  String get authEmailExists => '该邮箱已注册。';

  @override
  String get authNetworkError => '无法连接服务器，请检查网络后重试。';

  @override
  String get authRegisterFailed => '注册失败，请重试。';

  @override
  String get authForgotPassword => '忘记密码？';

  @override
  String get authForgotPasswordTitle => '重置密码';

  @override
  String get authForgotPasswordDesc => '输入邮箱以获取重置令牌。';

  @override
  String get authSendResetLink => '发送重置令牌';

  @override
  String get authSending => '发送中…';

  @override
  String get authResetToken => '重置令牌';

  @override
  String get authResetTokenPlaceholder => '粘贴重置令牌';

  @override
  String get authNewPassword => '新密码';

  @override
  String get authConfirmReset => '重置密码';

  @override
  String get authResetting => '重置中…';

  @override
  String get authResetSent => '若该账号存在，已签发重置令牌。';

  @override
  String get authPasswordReset => '密码已重置，请登录。';

  @override
  String get authResetFailed => '重置失败，令牌可能无效或已过期。';

  @override
  String get authBackToLogin => '返回登录';

  @override
  String get authConfirmPassword => '确认密码';

  @override
  String get legalTrademark => 'CISSP® 和 ISC2® 是 ISC2, Inc. 的注册商标。';

  @override
  String get legalNotOfficial => '本产品为独立学习工具，并非官方 ISC2 考试平台，亦未获得 ISC2 关联或认可。';

  @override
  String get dashboardEyebrow => '概览';

  @override
  String get dashboardTitle => '仪表盘';

  @override
  String get dashboardDescription => '一目了然查看你的 CISSP 学习概况。';

  @override
  String get dashboardContinuePractice => '继续练习';

  @override
  String get dashboardNoActivity => '暂无活动';

  @override
  String get dashboardNoActivityDesc => '开始一次练习，即可在此查看正确率、薄弱领域和复习建议。';

  @override
  String get dashboardStartPracticing => '开始练习';

  @override
  String get dashboardAccuracy => '正确率';

  @override
  String get dashboardAnswered => '已答';

  @override
  String get dashboardStudyTime => '学习时长';

  @override
  String get dashboardStreak => '连续';

  @override
  String dashboardStreakDays(int n) {
    return '$n天';
  }

  @override
  String dashboardCorrectOf(int c, int a) {
    return '$c/$a 正确';
  }

  @override
  String get dashboardPracticeTitle => '练习';

  @override
  String get dashboardPracticeDesc => '按领域与知识点进行定向练习。';

  @override
  String get dashboardMockExamTitle => '模拟考试';

  @override
  String get dashboardMockExamDesc => '固定卷与自适应（CAT）模考，训练考试节奏。';

  @override
  String get dashboardStartExamCta => '开始模考';

  @override
  String get dashboardReviewTitle => '复习';

  @override
  String get dashboardReviewDesc => '针对错题、收藏与标记题目进行再练。';

  @override
  String get dashboardReviewCta => '复习错题';

  @override
  String get dashboardWeakDomains => '薄弱领域';

  @override
  String get dashboardDomainMastery => '领域掌握度';

  @override
  String get dashboardLoading => '正在加载仪表盘…';

  @override
  String get dashboardLoadFailed => '无法加载仪表盘。';

  @override
  String get dashboardTodayRec => '今日建议';

  @override
  String get analyticsEyebrow => '洞察';

  @override
  String get analyticsTitle => '学习分析';

  @override
  String get analyticsDescription => '按时间维度查看你的表现明细。';

  @override
  String get analyticsPerformance => '表现';

  @override
  String get analyticsAccuracyTrend => '正确率趋势';

  @override
  String get analyticsMastery => '掌握度';

  @override
  String get analyticsDomainMastery => '领域掌握度';

  @override
  String get analyticsFocusAreas => '重点关注';

  @override
  String get analyticsWeakKp => '薄弱知识点';

  @override
  String get analyticsErrorTypes => '错误类型';

  @override
  String get analyticsLoading => '正在加载分析…';

  @override
  String get analyticsLoadFailed => '无法加载分析。';

  @override
  String get analyticsColDomain => '领域';

  @override
  String get analyticsColAccuracy => '正确率';

  @override
  String get analyticsColAnswered => '已答';

  @override
  String get practiceTitle => '练习';

  @override
  String get practiceDescription => '创建或恢复定向练习会话。';

  @override
  String get practiceNewSession => '新会话';

  @override
  String get practiceResume => '继续';

  @override
  String get practiceStart => '开始练习';

  @override
  String get practiceSubmit => '提交';

  @override
  String get practiceNext => '下一题';

  @override
  String get practiceFinish => '结束';

  @override
  String get practicePause => '暂停';

  @override
  String get practiceResumeAction => '恢复会话';

  @override
  String get practiceSessionPaused => '会话已暂停，恢复后继续。';

  @override
  String get practiceCorrect => '正确';

  @override
  String get practiceIncorrect => '错误';

  @override
  String get practiceSummaryTitle => '练习总结';

  @override
  String get practiceLoading => '加载中…';

  @override
  String get practiceCouldNotStart => '无法开始会话。';

  @override
  String get practiceAlreadyAnswered => '本题已作答。';

  @override
  String get practiceCount => '题量';

  @override
  String get practiceSubset => '范围';

  @override
  String get practiceOrder => '顺序';

  @override
  String get practiceDomain => '域';

  @override
  String get practiceAnyDomain => '任意域';

  @override
  String get practiceBook => '书本';

  @override
  String get practiceAnyBook => '任意书本';

  @override
  String get practiceChapter => '章节';

  @override
  String get practiceAnyChapter => '任意章节';

  @override
  String get practiceKeyPoints => '知识点';

  @override
  String get practiceOptionExplanations => '选项解析';

  @override
  String get practiceLanguage => '题目语言';

  @override
  String get practiceShuffleOptions => '打乱选项';

  @override
  String get practiceActiveSessions => '进行中的会话';

  @override
  String get practiceBookmark => '收藏';

  @override
  String get practiceFlag => '标记复习';

  @override
  String get practiceMastered => '已掌握';

  @override
  String get practiceQuestioned => '有疑问';

  @override
  String get practiceMapping => '知识点映射';

  @override
  String get practiceHistory => '历史作答';

  @override
  String get practiceRelated => '相关题目';

  @override
  String get practiceHistoryCorrect => '正确';

  @override
  String get practiceHistoryIncorrect => '错误';

  @override
  String get practiceDifficulty => '难度';

  @override
  String get practiceAnyDifficulty => '任意难度';

  @override
  String get practiceQuestionType => '题型';

  @override
  String get practiceAnyQuestionType => '任意题型';

  @override
  String get practiceTag => '标签';

  @override
  String get practiceAnyTag => '任意标签';

  @override
  String get questionTypeSingle => '单选';

  @override
  String get questionTypeMultiple => '多选';

  @override
  String get questionTypeTrueFalse => '判断';

  @override
  String get practiceNote => '笔记';

  @override
  String get practiceErrorType => '错误类型';

  @override
  String get practiceAnother => '再练一组';

  @override
  String get practiceBackHome => '返回练习';

  @override
  String get practiceAccuracy => '正确率';

  @override
  String get practiceTimeSpent => '用时';

  @override
  String get practiceDomains => '按域';

  @override
  String get practiceWrongList => '错题';

  @override
  String practiceQuestionOf(int current, int total) {
    return '第 $current / $total 题';
  }

  @override
  String get subsetAll => '全部';

  @override
  String get subsetUnpracticed => '未练';

  @override
  String get subsetWrong => '错题';

  @override
  String get subsetBookmarked => '收藏';

  @override
  String get subsetNeedsReview => '待复习';

  @override
  String get orderRandom => '随机';

  @override
  String get orderSequential => '顺序';

  @override
  String get orderEasyToHard => '由易到难';

  @override
  String get orderWeakFirst => '弱项优先';

  @override
  String get errorConceptUnclear => '概念不清';

  @override
  String get errorMisreadStem => '题干误读';

  @override
  String get errorMemoryLapse => '记忆模糊';

  @override
  String get errorOptionConfusion => '选项混淆';

  @override
  String get errorTimePressure => '时间压力';

  @override
  String get reviewTitle => '复习';

  @override
  String get reviewDescription => '再练错题、收藏与标记题目。';

  @override
  String get reviewWrong => '错题';

  @override
  String get reviewBookmarked => '收藏';

  @override
  String get reviewFlagged => '待复习';

  @override
  String get reviewWrongDesc => '再练答错的题目。';

  @override
  String get reviewBookmarkedDesc => '再练已收藏的题目。';

  @override
  String get reviewFlaggedDesc => '再练标记待复习的题目。';

  @override
  String get reviewStart => '开始复习会话';

  @override
  String get reviewCouldNotStart => '没有匹配题目，或无法开始。';

  @override
  String get examTitle => '模拟考试';

  @override
  String get examDescription => '固定卷与自适应（CAT）模考，训练考试节奏。';

  @override
  String get examNew => '新模考';

  @override
  String get examHistory => '历史';

  @override
  String get examFixedTitle => '固定模考';

  @override
  String get examCatTitle => 'CAT 模考';

  @override
  String get examStartFixed => '开始固定模考';

  @override
  String get examStartCat => '开始 CAT 模考';

  @override
  String get examReportTitle => '考试报告';

  @override
  String get examReviewTitle => '答题回顾';

  @override
  String get examFinish => '交卷';

  @override
  String get examTimeRemaining => '剩余时间';

  @override
  String get examPass => '通过';

  @override
  String get examFail => '未通过';

  @override
  String get examLoading => '正在加载考试…';

  @override
  String get examCatDisclaimer => '学习工具，非官方 ISC2 分数。仅可前进，提交后不可修改。';

  @override
  String get examAcknowledgeFixed => '我了解这是限时模拟考试。';

  @override
  String get examAcknowledgeCat => '我了解 CAT 仅可前进，提交后不可修改。';

  @override
  String get examResume => '继续考试';

  @override
  String get examActiveSessions => '进行中';

  @override
  String get examScore => '分数';

  @override
  String get examAccuracy => '正确率';

  @override
  String get examAbility => '能力估计';

  @override
  String get examSem => 'SEM';

  @override
  String get examReadiness => '就绪度';

  @override
  String get examYourAnswer => '你的答案';

  @override
  String get examCorrectAnswer => '正确答案';

  @override
  String get examTimeUp => '时间到，正在交卷。';

  @override
  String get examNotInProgress => '考试已不在进行中。';

  @override
  String get examCouldNotStart => '无法开始考试。';

  @override
  String get examViewReview => '回顾答题';

  @override
  String get examBackHome => '返回模考';

  @override
  String examQuestionOf(int current, int total) {
    return '第 $current / $total 题';
  }

  @override
  String get settingsTitle => '设置';

  @override
  String get settingsDescription => '管理界面语言与题目内容语言。';

  @override
  String get settingsInterfaceTitle => '界面语言';

  @override
  String get settingsInterfaceDesc => '选择菜单、按钮与标签的语言。';

  @override
  String get settingsContentTitle => '题目内容语言';

  @override
  String get settingsContentDesc => '选择题目的显示方式。';

  @override
  String get settingsSaved => '已保存。';

  @override
  String get settingsChangePasswordTitle => '修改密码';

  @override
  String get settingsChangePasswordDesc => '更新账户密码。';

  @override
  String get settingsCurrentPassword => '当前密码';

  @override
  String get settingsNewPassword => '新密码';

  @override
  String get settingsConfirmPassword => '确认新密码';

  @override
  String get settingsPasswordChanged => '密码已修改。';

  @override
  String get settingsPasswordMismatch => '两次密码不一致。';

  @override
  String get settingsPasswordIncorrect => '当前密码不正确。';

  @override
  String get settingsUpdating => '更新中…';

  @override
  String get settingsGoalsTitle => '学习目标';

  @override
  String get settingsGoalsDesc => '设置考试日期和每日答题目标，进度会显示在仪表盘上。';

  @override
  String settingsExamDateValue(Object date) {
    return '考试：$date';
  }

  @override
  String get settingsExamDateUnset => '设置考试日期';

  @override
  String get settingsExamDateClear => '清除';

  @override
  String get settingsDailyGoal => '每日目标';

  @override
  String get settingsGoalLess => '减少';

  @override
  String get settingsGoalMore => '增加';

  @override
  String get settingsGoalSet => '设为每天 20 题';

  @override
  String get dashboardTodayGoal => '今日';

  @override
  String dashboardTodayGoalValue(Object done, Object goal) {
    return '$done/$goal';
  }

  @override
  String get dashboardToExam => '距考试';

  @override
  String dashboardDaysToExam(num count) {
    return '$count 天';
  }
}
