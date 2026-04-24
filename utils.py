"""工具内的最小化并可靠的 utils.answer 实现。

目的：提供一个可被项目中其他模块（例如 `streamlit.py`）调用的、简单且可导入的 `answer` 函数。
实现策略：避免调用外部服务或复杂依赖，返回一个 (title, script) 的元组以兼容现有 UI。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple
import uuid
import time
from time import perf_counter
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from identify_fake import identify_fake


def answer(theme: str, style: Optional[str] = None, target: Optional[str] = None, creativity: float = 0.2, api_key: Optional[str] = None) -> Tuple[str, str]:
    """生成一个简单的摘要草稿，用于替代外部 AI 服务的调用。

    返回 (title, script)。这足够用于前端展示与后续替换为真实模型调用。
    """
    if not theme:
        theme = "(未提供主题)"
    title = f"主题：{theme}"
    style_str = f"风格：{style}" if style else "风格：默认"
    target_str = f"目标受众：{target}" if target else "目标受众：通用读者"
    script = (
        f"{title}\n{style_str}\n{target_str}\n\n这是一个自动生成的草稿（占位）。\n"
        f"创造性参数：{creativity}\n\n" 
        f"简要：针对‘{theme}’的调研摘要（请替换为真实模型返回）。"
    )
    return title, script


@dataclass
class AIProvider:
    name: str
    timeout_s: float = 8.0
    max_attempts: int = 2
    circuit_fail_threshold: int = 3
    circuit_cooldown_s: int = 60
    _fail_streak: int = field(default=0, init=False, repr=False)
    _circuit_open_until: float = field(default=0.0, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def infer(self, theme: str, style: str, target: str, creativity: float, api_key: str = "") -> Dict:
        raise NotImplementedError

    def mark_success(self):
        with self._lock:
            self._fail_streak = 0
            self._circuit_open_until = 0.0

    def mark_failure(self):
        with self._lock:
            self._fail_streak += 1
            if self._fail_streak >= self.circuit_fail_threshold:
                self._circuit_open_until = time.time() + float(self.circuit_cooldown_s)

    def is_circuit_open(self) -> bool:
        with self._lock:
            return time.time() < self._circuit_open_until

    def circuit_state(self) -> Dict:
        with self._lock:
            remaining = max(0, int(self._circuit_open_until - time.time()))
            return {
                "fail_streak": self._fail_streak,
                "is_open": remaining > 0,
                "cooldown_left_s": remaining,
            }


class GPTProvider(AIProvider):
    def __init__(self):
        super().__init__(name="GPT")

    def infer(self, theme: str, style: str, target: str, creativity: float, api_key: str = "") -> Dict:
        title, script = answer(theme=theme, style=style, target=target, creativity=creativity, api_key=api_key)
        return {
            "text": f"[{title}]\n{script}",
            "score": 0.82,
            "meta": {"model": "gpt-placeholder"},
        }


class GeminiProvider(AIProvider):
    def __init__(self):
        super().__init__(name="Gemini")

    def infer(self, theme: str, style: str, target: str, creativity: float, api_key: str = "") -> Dict:
        return {
            "text": f"Gemini视角：围绕主题“{theme}”，建议先做问题定义，再做证据分层，最后给出可验证结论。",
            "score": 0.76,
            "meta": {"model": "gemini-placeholder"},
        }


class DeepSeekProvider(AIProvider):
    def __init__(self):
        super().__init__(name="DeepSeek")

    def infer(self, theme: str, style: str, target: str, creativity: float, api_key: str = "") -> Dict:
        return {
            "text": f"DeepSeek视角：对“{theme}”可按“背景-方法-实验-风险”四段式输出，便于后续审阅和追踪。",
            "score": 0.79,
            "meta": {"model": "deepseek-placeholder"},
        }


class WeightedResultAggregator:
    """Simple weighted aggregation with deterministic fallback."""

    def __init__(self, weights: Dict[str, float] | None = None):
        self.weights = weights or {
            "GPT": 1.0,
            "Gemini": 0.9,
            "DeepSeek": 0.95,
            "LocalDetector": 0.7,
        }

    def aggregate(self, provider_outputs: Dict[str, Dict]) -> Dict:
        if not provider_outputs:
            return {
                "final_text": "无可用模型输出",
                "confidence": 0.0,
                "winner": "none",
                "details": {},
            }

        scored = {}
        for name, output in provider_outputs.items():
            base_score = float(output.get("score", 0.0))
            weight = float(self.weights.get(name, 0.8))
            scored[name] = base_score * weight

        winner = max(scored, key=scored.get)
        confidence = min(1.0, max(0.0, scored[winner]))
        return {
            "final_text": provider_outputs[winner].get("text", ""),
            "confidence": confidence,
            "winner": winner,
            "details": {
                "scored": scored,
                "raw": provider_outputs,
            },
        }


class OnlineValidator:
    """Rule-based validation to provide reliability hints."""

    def validate(self, aggregated: Dict) -> Dict:
        text = (aggregated.get("final_text") or "").strip()
        confidence = float(aggregated.get("confidence", 0.0))

        issues: List[str] = []
        warnings: List[str] = []

        if not text:
            issues.append("输出为空")
        elif len(text) < 30:
            warnings.append("输出较短，信息可能不足")

        if confidence < 0.5:
            warnings.append("融合置信度偏低，建议人工复核")

        if "占位" in text:
            warnings.append("结果包含占位内容，建议替换为真实模型输出")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "score": max(0.0, 1.0 - 0.2 * len(issues) - 0.1 * len(warnings)),
        }


@dataclass
class PipelineInput:
    theme: str
    style: str = "默认"
    target: str = "通用读者"
    creativity: float = 0.2
    api_key: str = ""
    run_training: bool = False


@dataclass
class PipelineResult:
    trace_id: str
    stage_logs: List[str] = field(default_factory=list)
    stage_timing_ms: Dict[str, int] = field(default_factory=dict)
    provider_metrics: Dict[str, Dict] = field(default_factory=dict)
    fetched_data: Dict = field(default_factory=dict)
    processed_data: Dict = field(default_factory=dict)
    training_metrics: Optional[Dict] = None
    provider_outputs: Dict[str, Dict] = field(default_factory=dict)
    aggregated_output: Dict = field(default_factory=dict)
    validation: Dict = field(default_factory=dict)


class PipelineOrchestrator:
    """Linear + branch AI pipeline orchestrator."""

    def __init__(
        self,
        providers: Optional[List[AIProvider]] = None,
        aggregator: Optional[WeightedResultAggregator] = None,
        validator: Optional[OnlineValidator] = None,
    ):
        self.providers = providers or [
            GPTProvider(),
            GeminiProvider(),
            DeepSeekProvider(),
        ]
        self.aggregator = aggregator or WeightedResultAggregator()
        self.validator = validator or OnlineValidator()

    def run(self, data: PipelineInput, on_stage: Optional[Callable[[str], None]] = None) -> PipelineResult:
        trace_id = uuid.uuid4().hex
        result = PipelineResult(trace_id=trace_id)
        stage_begin_ts: Optional[float] = None

        def start_stage():
            nonlocal stage_begin_ts
            stage_begin_ts = perf_counter()

        def mark_stage_end(stage_name: str):
            if stage_begin_ts is None:
                result.stage_timing_ms[stage_name] = 0
                return
            elapsed = int((perf_counter() - stage_begin_ts) * 1000)
            result.stage_timing_ms[stage_name] = elapsed

        def log(msg: str):
            line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
            result.stage_logs.append(line)
            if on_stage:
                on_stage(line)

        start_stage()
        log(f"启动流水线，trace_id={trace_id}")
        log("阶段1/7 用户触发")
        mark_stage_end("user_trigger")

        start_stage()
        log("阶段2/7 数据采集")
        collection_mode = "fallback_mock"
        collection_error = ""
        records = []
        try:
            # 懒加载，避免在启动时引入重依赖或循环导入
            import requests
            from import_requests import search_cnki

            session = requests.Session()
            real_records = search_cnki(session=session, topic=data.theme, max_results=10)
            if isinstance(real_records, list) and len(real_records) > 0:
                records = real_records
                collection_mode = "cnki_search"
            else:
                collection_error = "真实检索返回为空"
        except Exception as e:
            collection_error = str(e)

        if not records:
            records = [
                {"title": data.theme, "snippet": f"{data.theme} 相关资料片段 A"},
                {"title": data.theme, "snippet": f"{data.theme} 相关资料片段 B"},
            ]

        result.fetched_data = {
            "source": collection_mode,
            "records": records,
            "error": collection_error,
        }
        mark_stage_end("collect_data")

        start_stage()
        log("阶段3/7 数据预处理")
        result.processed_data = {
            "theme": data.theme,
            "style": data.style,
            "target": data.target,
            "creativity": data.creativity,
            "record_count": len(result.fetched_data.get("records", [])),
            "collection_mode": collection_mode,
        }
        mark_stage_end("preprocess")

        start_stage()
        if data.run_training:
            log("阶段4/7 模型训练与验证")
            result.training_metrics = {
                "accuracy": 0.86,
                "loss": 0.41,
                "epoch": 5,
                "note": "占位训练结果，可接入 neural_network.train_model",
            }
        else:
            log("阶段4/7 跳过训练（按配置）")
        mark_stage_end("train_or_skip")

        start_stage()
        log("阶段5/7 多模型推理")

        def call_provider(provider: AIProvider):
            begin = perf_counter()
            max_attempts = max(1, int(provider.max_attempts))
            last_error = ""

            if provider.is_circuit_open():
                state = provider.circuit_state()
                return provider.name, {
                    "text": f"{provider.name} 暂时熔断中，请稍后重试（剩余 {state.get('cooldown_left_s', 0)}s）",
                    "score": 0.0,
                    "meta": {"error": "circuit_open", "state": state},
                }, {
                    "attempts": 0,
                    "success": False,
                    "latency_ms": 0,
                    "error": "circuit_open",
                    "timeout_s": provider.timeout_s,
                    "circuit": state,
                }

            for attempt in range(1, max_attempts + 1):
                try:
                    with ThreadPoolExecutor(max_workers=1) as single_exec:
                        future = single_exec.submit(
                            provider.infer,
                            data.theme,
                            data.style,
                            data.target,
                            data.creativity,
                            data.api_key,
                        )
                        output = future.result(timeout=float(provider.timeout_s))
                    provider.mark_success()
                    return provider.name, output, {
                        "attempts": attempt,
                        "success": True,
                        "latency_ms": int((perf_counter() - begin) * 1000),
                        "error": "",
                        "timeout_s": provider.timeout_s,
                        "circuit": provider.circuit_state(),
                    }
                except FuturesTimeoutError:
                    last_error = f"timeout>{provider.timeout_s}s"
                    provider.mark_failure()
                except Exception as e:
                    last_error = str(e)
                    provider.mark_failure()

            return provider.name, {
                "text": f"{provider.name} 推理失败: {last_error}",
                "score": 0.0,
                "meta": {"error": last_error},
            }, {
                "attempts": max_attempts,
                "success": False,
                "latency_ms": int((perf_counter() - begin) * 1000),
                "error": last_error,
                "timeout_s": provider.timeout_s,
                "circuit": provider.circuit_state(),
            }

        # 线程并发执行多模型推理，减少总时延
        with ThreadPoolExecutor(max_workers=max(1, len(self.providers))) as executor:
            futures = [executor.submit(call_provider, provider) for provider in self.providers]
            for future in as_completed(futures):
                name, output, metric = future.result()
                result.provider_outputs[name] = output
                result.provider_metrics[name] = metric
                status = "成功" if metric.get("success") else "失败"
                log(f"- {name} 返回完成（{status}，{metric.get('latency_ms', 0)}ms，重试{max(0, metric.get('attempts', 1)-1)}次）")
        mark_stage_end("multi_infer")

        start_stage()
        detector_msg = identify_fake(theme=data.theme, style=data.style, creativity=data.creativity)
        result.provider_outputs["LocalDetector"] = {
            "text": detector_msg,
            "score": 0.68,
            "meta": {"source": "identify_fake"},
        }
        result.provider_metrics["LocalDetector"] = {
            "attempts": 1,
            "success": True,
            "latency_ms": 0,
            "error": "",
        }
        log("- LocalDetector 返回完成")
        mark_stage_end("local_detector")

        start_stage()
        log("阶段6/7 结果综合")
        result.aggregated_output = self.aggregator.aggregate(result.provider_outputs)
        mark_stage_end("aggregate")

        start_stage()
        log("阶段7/7 在线验证")
        result.validation = self.validator.validate(result.aggregated_output)
        mark_stage_end("validate")

        retry_total = sum(max(0, metric.get("attempts", 1) - 1) for metric in result.provider_metrics.values())
        result.processed_data["provider_retry_total"] = retry_total
        result.processed_data["provider_circuit_state"] = {
            provider.name: provider.circuit_state() for provider in self.providers
        }

        log("流水线结束")
        return result


_GLOBAL_ORCHESTRATOR: Optional[PipelineOrchestrator] = None


def _get_orchestrator() -> PipelineOrchestrator:
    global _GLOBAL_ORCHESTRATOR
    if _GLOBAL_ORCHESTRATOR is None:
        _GLOBAL_ORCHESTRATOR = PipelineOrchestrator()
    return _GLOBAL_ORCHESTRATOR


def run_quick_pipeline(
    theme: str,
    style: str,
    target: str,
    creativity: float,
    api_key: str,
    run_training: bool,
    provider_timeout_s: float = 8.0,
    provider_max_attempts: int = 2,
    circuit_fail_threshold: int = 3,
    circuit_cooldown_s: int = 60,
):
    """Compatibility helper for UI integration."""
    orchestrator = _get_orchestrator()

    # 允许运行时动态调整模型调度策略
    for provider in orchestrator.providers:
        provider.timeout_s = max(1.0, float(provider_timeout_s))
        provider.max_attempts = max(1, int(provider_max_attempts))
        provider.circuit_fail_threshold = max(1, int(circuit_fail_threshold))
        provider.circuit_cooldown_s = max(1, int(circuit_cooldown_s))

    data = PipelineInput(
        theme=theme,
        style=style or "默认",
        target=target or "通用读者",
        creativity=creativity,
        api_key=api_key or "",
        run_training=run_training,
    )
    return orchestrator.run(data)
