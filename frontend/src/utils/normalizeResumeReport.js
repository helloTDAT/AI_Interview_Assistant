const pickScore = (scores, names, fallback) => {
  for (const name of names) {
    if (typeof scores?.[name] === "number") return clamp(scores[name]);
  }
  return clamp(fallback);
};

const clamp = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
};

const asArray = (value) => (Array.isArray(value) ? value : []);

export function normalizeResumeReport(report = {}) {
  const profile = report.profile || {};
  const jobFit = report.job_fit || {};
  const reading = report.reading_experience || {};
  const rawScores = report.dimension_scores || {};
  const projects = asArray(profile.projects);
  const skills = asArray(profile.skills);
  const fitScore = clamp(jobFit.fit_score ?? report.jd_diagnosis?.match_rate ?? 0);
  const confidence = clamp((profile.parse_confidence ?? 0) * 100);

  const dimensionScores = {
    专业技能: pickScore(rawScores, ["专业技能", "技能匹配", "鎶€鑳藉尮閰?", "鎶€鑳藉尮閰"], 45 + skills.length * 8),
    项目经验: pickScore(rawScores, ["项目经验", "项目表达", "椤圭洰琛ㄨ揪"], projects.length ? 82 : 54),
    岗位匹配: pickScore(rawScores, ["岗位匹配", "岗位适配", "宀椾綅鍖归厤"], fitScore),
    表达量化: pickScore(rawScores, ["表达量化", "量化表达", "琛ㄨ揪閲忓寲"], reading.signal_to_noise_score ?? 68),
    教育背景: pickScore(rawScores, ["教育背景", "完整度", "瀹屾暣搴?"], asArray(profile.education).length ? 80 : 58),
    软技能: pickScore(rawScores, ["软技能", "沟通协作", "杞妧鑳?"], 70),
  };

  const expectedSkills = asArray(jobFit.expected_skills);
  const matchedSkills = asArray(jobFit.matched_skills);
  const missingSkills = asArray(jobFit.missing_skills);
  const jd = report.jd_diagnosis || {};

  return {
    source: report,
    qualityScore: clamp(report.quality_score),
    dimensionScores,
    targetPosition: jobFit.target_position || profile.target_position || "目标岗位未填写",
    analysisEngine: report.analysis_engine || "rules",
    needsUserConfirmation: Boolean(report.needs_user_confirmation),
    parseConfidence: confidence,
    profile,
    templateSimilarityScore: clamp(report.template_similarity_score),
    forbiddenWords: asArray(report.forbidden_words),
    jobFit: {
      ...jobFit,
      fit_score: fitScore,
      expected_skills: expectedSkills,
      matched_skills: matchedSkills,
      missing_skills: missingSkills,
    },
    jdDiagnosis: {
      enabled: Boolean(jd.enabled),
      match_rate: clamp(jd.match_rate ?? fitScore),
      core_requirements: asArray(jd.core_requirements).length ? asArray(jd.core_requirements) : expectedSkills,
      matched_items: asArray(jd.matched_items).length ? asArray(jd.matched_items) : matchedSkills,
      missing_items: asArray(jd.missing_items).length ? asArray(jd.missing_items) : missingSkills,
      suggestions: asArray(jd.suggestions),
    },
    interviewRisks: asArray(report.interview_risks),
    logicGaps: asArray(report.logic_gaps),
    readingExperience: {
      signal_to_noise_score: clamp(reading.signal_to_noise_score ?? 75),
      cliches: asArray(reading.cliches),
      density_notes: asArray(reading.density_notes),
      suggestions: asArray(reading.suggestions),
    },
    starOptimizations: asArray(report.star_optimizations),
    recommendations: asArray(report.recommendations),
  };
}
