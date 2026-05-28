from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models import ResumeAnalysisReport
from app.services.ai_clients import LLMClient
from app.services.resume_parser import ResumeParser


class ResumeEvaluationAgent:
    forbidden_words = ["精通所有", "绝对", "包过", "代写", "虚假", "造假"]

    target_skill_map = {
        "后端": ["Java", "Python", "SQL", "MySQL", "Redis", "Spring", "Netty", "RocketMQ", "Docker", "Linux"],
        "Java": ["Java", "Spring", "MySQL", "Redis", "JVM", "并发", "Netty", "RocketMQ"],
        "Python": ["Python", "SQL", "Redis", "FastAPI", "Docker", "Linux"],
        "前端": ["JavaScript", "TypeScript", "React", "Vue", "工程化"],
        "AI": ["Python", "机器学习", "深度学习", "PyTorch", "TensorFlow", "算法", "SQL"],
        "算法": ["Python", "机器学习", "深度学习", "PyTorch", "TensorFlow", "算法", "SQL"],
        "数据分析": ["Python", "SQL", "数据分析", "可视化", "机器学习"],
        "产品": ["需求分析", "用户研究", "原型设计", "数据分析"],
        "测试": ["测试用例", "自动化测试", "Python", "接口测试", "性能测试"],
    }
    weak_heading_tokens = {"项目背景", "工作内容", "项目描述", "项目成果", "项目经历", "技术栈", "个人职责", "优化", "提升", "主导"}
    action_words = ["负责", "参与", "主导", "设计", "实现", "完成", "优化", "重构", "封装", "接入", "迁移", "压测", "部署", "沉淀"]

    def __init__(self, parser: ResumeParser | None = None, llm: LLMClient | None = None) -> None:
        self.parser = parser or ResumeParser()
        self.llm = llm or LLMClient()

    def analyze(
        self,
        path: Path,
        target_position: str | None = None,
        user_instruction: str | None = None,
        job_description: str | None = None,
    ) -> ResumeAnalysisReport:
        profile = self.parser.parse(path)
        target = target_position or profile.target_position or "目标岗位未填写"
        base_report = self._build_rule_report(profile, target, user_instruction, job_description)

        llm_result = self.llm.analyze_resume_report(profile, target, user_instruction, job_description)
        if not llm_result.ok or not llm_result.data:
            if llm_result.error != "chatanywhere api key is not configured":
                base_report.analysis_engine = "rules_fallback"
                base_report.llm_error = llm_result.error
            return base_report

        try:
            return self._merge_llm_report(base_report, llm_result.data)
        except (TypeError, ValueError, KeyError) as exc:
            base_report.analysis_engine = "rules_fallback"
            base_report.llm_error = f"llm schema invalid: {exc}"
            return base_report

    def _build_rule_report(
        self,
        profile,
        target: str,
        user_instruction: str | None,
        job_description: str | None,
    ) -> ResumeAnalysisReport:
        forbidden_hits = [word for word in self.forbidden_words if word in profile.raw_text]
        dimension_scores = self._score_dimensions(profile)
        job_fit = self._job_fit(profile.skills, target, profile.raw_text, job_description)
        quality_score = round(
            dimension_scores["完整度"] * 0.3
            + dimension_scores["技能匹配"] * 0.25
            + dimension_scores["项目表达"] * 0.25
            + dimension_scores["可信度"] * 0.2
        )
        recommendations = self._recommend(profile, forbidden_hits, job_fit["missing_skills"], user_instruction)
        needs_confirmation = profile.parse_confidence < 0.6 or bool(profile.warnings) or not profile.raw_text.strip()
        return ResumeAnalysisReport(
            profile=profile,
            quality_score=quality_score,
            dimension_scores=dimension_scores,
            forbidden_words=forbidden_hits,
            template_similarity_score=self._template_similarity(profile.raw_text),
            job_fit=job_fit,
            recommendations=recommendations,
            analysis_engine="rules",
            jd_diagnosis=self._rule_jd_diagnosis(job_fit, job_description),
            interview_risks=self._rule_interview_risks(profile),
            logic_gaps=self._rule_logic_gaps(profile),
            reading_experience=self._rule_reading_experience(profile.raw_text),
            star_optimizations=self._rule_star_optimizations(profile),
            needs_user_confirmation=needs_confirmation,
        )

    def _merge_llm_report(self, base: ResumeAnalysisReport, data: dict[str, Any]) -> ResumeAnalysisReport:
        report_data = base.model_dump(mode="python")
        report_data["quality_score"] = self._clamp_score(data.get("quality_score", base.quality_score))
        report_data["dimension_scores"] = self._score_dict(data.get("dimension_scores")) or base.dimension_scores
        report_data["job_fit"] = self._merge_job_fit(base.job_fit, data.get("job_fit"))
        report_data["recommendations"] = self._string_list(data.get("recommendations")) or base.recommendations
        report_data["jd_diagnosis"] = self._merge_dict(base.jd_diagnosis, data.get("jd_diagnosis"))
        report_data["interview_risks"] = self._valid_risk_items(data.get("interview_risks")) or base.interview_risks
        report_data["logic_gaps"] = self._object_list(data.get("logic_gaps")) or base.logic_gaps
        report_data["reading_experience"] = self._merge_dict(base.reading_experience, data.get("reading_experience"))
        report_data["star_optimizations"] = self._valid_star_items(data.get("star_optimizations")) or base.star_optimizations
        report_data["analysis_engine"] = "llm"
        report_data["llm_error"] = None
        return ResumeAnalysisReport(**report_data)

    def _score_dimensions(self, profile) -> dict[str, int]:
        completeness = 40
        completeness += 10 if profile.candidate_name else 0
        completeness += 10 if profile.contact else 0
        completeness += 15 if profile.education else 0
        completeness += 15 if profile.projects or profile.internships else 0
        completeness += 10 if profile.skills else 0
        skill_score = min(95, 45 + len(profile.skills) * 7)
        project_score = 88 if profile.projects else 76 if profile.internships else 55
        credibility = int(profile.parse_confidence * 100)
        return {
            "完整度": min(completeness, 100),
            "技能匹配": skill_score,
            "项目表达": project_score,
            "可信度": credibility,
        }

    def _job_fit(self, skills: list[str], target: str, resume_text: str = "", job_description: str | None = None) -> dict:
        expected = ["Python", "SQL", "项目经历"]
        for keyword, required in self.target_skill_map.items():
            if keyword in target:
                expected = required
                break
        if job_description:
            jd_terms = self._extract_jd_terms(job_description)
            if jd_terms:
                expected = list(dict.fromkeys([*expected, *jd_terms]))[:14]
        haystack = f"{resume_text}\n{' '.join(skills)}".lower()
        matched = [skill for skill in expected if skill.lower() in haystack]
        missing = [skill for skill in expected if skill not in matched]
        return {
            "target_position": target,
            "fit_score": round(len(matched) / max(len(expected), 1) * 100),
            "expected_skills": expected,
            "matched_skills": matched,
            "missing_skills": missing,
        }

    def _extract_jd_terms(self, text: str) -> list[str]:
        known = [
            "Python",
            "Java",
            "SQL",
            "MySQL",
            "Redis",
            "Docker",
            "Kubernetes",
            "K8s",
            "微服务",
            "FastAPI",
            "Spring",
            "React",
            "Vue",
            "PyTorch",
            "TensorFlow",
            "机器学习",
            "深度学习",
            "NLP",
            "大模型",
            "数据分析",
        ]
        return [term for term in known if term.lower() in text.lower()]

    def _template_similarity(self, text: str) -> int:
        generic_markers = ["本人性格开朗", "吃苦耐劳", "服从安排", "熟练使用办公软件"]
        hits = sum(1 for marker in generic_markers if marker in text)
        return min(100, hits * 25)

    def _recommend(
        self,
        profile,
        forbidden_hits: list[str],
        missing_skills: list[str],
        user_instruction: str | None,
    ) -> list[str]:
        tips: list[str] = []
        instruction = user_instruction or ""
        if profile.parse_confidence < 0.6:
            tips.append("当前文件解析置信度较低，只能作为预分析；请先确认 OCR/文本抽取结果，再进行正式评分。")
        if forbidden_hits:
            tips.append(f"删除或改写风险词：{', '.join(forbidden_hits)}。")
        if missing_skills:
            tips.append(f"围绕目标岗位补充证据：{', '.join(missing_skills[:6])}。")
        if "项目" in instruction:
            tips.append("项目经历建议按 STAR 法则重写：背景、行动、工具、个人贡献、量化结果。")
        if "AI" in instruction or "算法" in instruction:
            tips.append("AI/算法岗位需要突出 Python、模型选择、特征工程、评估指标、实验对比和落地效果。")
        if not profile.projects and not profile.internships and profile.parse_confidence >= 0.6:
            tips.append("增加 1-2 个项目经历，并用背景、行动、结果说明个人贡献。")
        if not tips:
            tips.append("简历基础结构完整，建议继续量化项目结果，并对齐目标岗位 JD。")
        return tips

    def _rule_jd_diagnosis(self, job_fit: dict, job_description: str | None) -> dict[str, Any]:
        enabled = bool(job_description and job_description.strip())
        return {
            "enabled": enabled,
            "match_rate": job_fit["fit_score"] if enabled else None,
            "core_requirements": job_fit["expected_skills"] if enabled else [],
            "matched_items": job_fit["matched_skills"] if enabled else [],
            "missing_items": job_fit["missing_skills"] if enabled else [],
            "suggestions": [
                "根据 JD 中反复出现的技能词，调整项目经历的技术侧重点。",
                "对缺失项补充学习、项目或实习证据；没有真实经历时不要硬写。",
            ]
            if enabled
            else ["未提供具体 JD，当前使用目标岗位画像进行通用匹配。"],
        }

    def _rule_interview_risks(self, profile) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        for segment in self._experience_segments(profile):
            if not self._is_concrete_experience(segment):
                continue
            risk_point = self._risk_point(segment)
            risks.append(
                {
                    "risk_point": risk_point,
                    "question": f"你在经历中写到“{self._shorten(segment, 52)}”。请说明当时的背景、你负责的具体模块、关键技术取舍和可验证结果。",
                    "why_it_matters": "这类表述有真实技术线索，面试官通常会追问你是否真正负责过核心设计。",
                    "defense_tip": "准备上下游链路、数据规模、关键决策、指标变化和复盘边界。",
                    "severity": "medium",
                }
            )
            if len(risks) >= 4:
                break
        if not risks:
            risks.append(
                {
                    "risk_point": "项目细节",
                    "question": "请选择一个最有代表性的项目，说明你的具体贡献、关键技术决策和量化结果。",
                    "why_it_matters": "当前可解析文本中的项目证据还不够突出。",
                    "defense_tip": "用 STAR 法则准备 1 分钟项目说明。",
                    "severity": "low",
                }
            )
        return risks

    def _rule_logic_gaps(self, profile) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        evidence_text = "\n".join([*profile.projects, *profile.internships]).lower()
        if not evidence_text:
            return gaps
        for skill in profile.skills:
            if skill.lower() in evidence_text:
                continue
            if skill in {"SQL", "Linux"} and skill.lower() in profile.raw_text.lower():
                continue
            gaps.append(
                {
                    "issue": f"技能“{skill}”缺少项目支撑",
                    "evidence": "技能栏出现该能力，但项目/实习经历中没有明显使用场景。",
                    "suggestion": f"在相关经历中补充 {skill} 的任务、方法和结果，或降低技能熟练度表述。",
                    "severity": "medium",
                }
            )
        return gaps[:3]

    def _rule_reading_experience(self, text: str) -> dict[str, Any]:
        cliches = [word for word in ["吃苦耐劳", "性格开朗", "认真负责", "服从安排"] if word in text]
        long_lines = [line for line in text.splitlines() if len(line.strip()) > 110]
        return {
            "signal_to_noise_score": max(50, 90 - len(cliches) * 10 - len(long_lines) * 4),
            "cliches": cliches,
            "density_notes": [f"发现 {len(long_lines)} 处长句，建议拆分为项目符号。"] if long_lines else [],
            "suggestions": ["减少套话，用行动证据替代性格评价。"] if cliches else ["保持项目符号清晰，优先展示岗位相关证据。"],
        }

    def _rule_star_optimizations(self, profile) -> list[dict[str, Any]]:
        source = next((item for item in self._experience_segments(profile) if self._is_concrete_experience(item)), "")
        if not source:
            source = "参与项目开发，完成相关功能。"
        return [
            {
                "before": self._shorten(source, 140),
                "after": "建议改写为：在明确业务背景下，说明你负责的具体模块、采用的技术方案、解决的关键问题，并补充可验证的量化结果。",
                "action_note": "补齐 STAR：情境、任务、行动、结果；保留真实指标，不要编造不存在的数据。",
            }
        ]

    def _experience_segments(self, profile) -> list[str]:
        text = "\n".join([*profile.projects, *profile.internships])
        segments: list[str] = []
        for line in re.split(r"[\n。；;]", text):
            cleaned = re.sub(r"^[\s•·●■\-]+", "", line.strip())
            if cleaned and not self._is_heading_only(cleaned):
                segments.append(cleaned)
        return segments

    def _is_heading_only(self, text: str) -> bool:
        normalized = re.sub(r"[\s【】\[\]（）():：]", "", text)
        return normalized in self.weak_heading_tokens or bool(re.fullmatch(r"项目经历\d*", normalized))

    def _is_concrete_experience(self, text: str) -> bool:
        if self._is_heading_only(text):
            return False
        has_action = any(word in text for word in self.action_words)
        has_anchor = bool(re.search(r"\d|%|Redis|MySQL|Netty|KMS|RocketMQ|WebRTC|Python|Java|SQL|Docker|Spring|Trace|API|ES", text, re.I))
        return has_action and has_anchor and len(text) >= 18

    def _risk_point(self, text: str) -> str:
        for term in ["布隆过滤器", "KMS", "Redis", "MySQL", "Netty", "RocketMQ", "WebRTC", "asyncio", "PyTorch", "Docker", "Trace ID"]:
            if term.lower() in text.lower():
                return term
        for action in self.action_words:
            if action in text:
                return action
        return "项目细节"

    def _valid_risk_items(self, value: Any) -> list[dict[str, Any]]:
        items = self._object_list(value)
        return [item for item in items if not self._is_heading_only(str(item.get("risk_point") or item.get("question") or ""))]

    def _valid_star_items(self, value: Any) -> list[dict[str, Any]]:
        items = self._object_list(value)
        return [item for item in items if not self._is_heading_only(str(item.get("before") or ""))]

    def _shorten(self, text: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        return compact if len(compact) <= limit else f"{compact[:limit]}..."

    def _merge_dict(self, base: dict[str, Any], value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return base
        merged = dict(base)
        merged.update(value)
        return merged

    def _merge_job_fit(self, base: dict[str, Any], value: Any) -> dict[str, Any]:
        merged = self._merge_dict(base, value)
        for key in ["expected_skills", "matched_skills", "missing_skills"]:
            if not merged.get(key):
                merged[key] = base.get(key, [])
        if merged.get("fit_score") is None:
            merged["fit_score"] = base.get("fit_score", 0)
        if not merged.get("target_position"):
            merged["target_position"] = base.get("target_position")
        return merged

    def _score_dict(self, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        return {str(key): self._clamp_score(score) for key, score in value.items()}

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()][:10]

    def _object_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)][:10]

    def _clamp_score(self, value: Any) -> int:
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            raise ValueError(f"invalid score: {value}")
        return max(0, min(100, score))
