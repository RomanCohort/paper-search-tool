"""数据驱动 AI 应用的 Streamlit 前端入口。"""

import streamlit as st
from utils import run_quick_pipeline


def main():
    st.title("探路者科研助手(●'◡'●)")
    st.caption("前端交互 -> 数据处理 -> 多模型推理 -> 结果融合 -> 在线验证")

    theme = st.text_input("请输入你感兴趣的主题🤞")
    style = st.text_input("请输入AI的说话风格😘")
    target = st.text_input("目标受众（可选）")
    creativity = st.slider("请选择回答的创造性🤩", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    api_key = st.text_input("请输入你的API Key（可选）😎")
    run_training = st.checkbox("启用训练验证阶段（演示占位）", value=False)

    with st.expander("模型调度策略"):
        provider_timeout_s = st.slider("单模型超时（秒）", min_value=1, max_value=30, value=8, step=1)
        provider_max_attempts = st.slider("单模型最大尝试次数", min_value=1, max_value=4, value=2, step=1)
        circuit_fail_threshold = st.slider("熔断阈值（连续失败次数）", min_value=1, max_value=6, value=3, step=1)
        circuit_cooldown_s = st.slider("熔断冷却时间（秒）", min_value=5, max_value=300, value=60, step=5)

    agree = st.checkbox("我确认本工具为练习项目，结果仅供参考")

    if st.button("点击生成"):
        if not agree:
            st.warning("请先勾选确认框再生成。")
        else:
            with st.spinner("别吵，AI在思考..."):
                result = run_quick_pipeline(
                    theme=theme,
                    style=style,
                    target=target,
                    creativity=creativity,
                    api_key=api_key,
                    run_training=run_training,
                    provider_timeout_s=float(provider_timeout_s),
                    provider_max_attempts=int(provider_max_attempts),
                    circuit_fail_threshold=int(circuit_fail_threshold),
                    circuit_cooldown_s=int(circuit_cooldown_s),
                )
            st.success("已完成！")

            st.subheader("最终输出")
            st.write(result.aggregated_output.get("final_text", ""))

            st.subheader("融合信息")
            c1, c2 = st.columns(2)
            with c1:
                st.metric("融合胜出模型", result.aggregated_output.get("winner", "-"))
            with c2:
                st.metric("融合置信度", f"{result.aggregated_output.get('confidence', 0.0):.2f}")

            st.subheader("在线验证")
            validation = result.validation
            if validation.get("passed"):
                st.success("校验通过")
            else:
                st.error("校验未通过")
            st.write(validation)

            with st.expander("查看阶段日志"):
                for line in result.stage_logs:
                    st.text(line)

            with st.expander("查看阶段耗时（ms）"):
                st.json(result.stage_timing_ms)

            with st.expander("查看多模型原始输出"):
                st.json(result.provider_outputs)

            with st.expander("查看模型调度指标"):
                st.json(result.provider_metrics)

            if result.training_metrics:
                with st.expander("训练验证指标"):
                    st.json(result.training_metrics)

            with st.expander("运行元信息"):
                st.text(f"trace_id: {result.trace_id}")
                st.json(result.processed_data)
                st.text(f"collection_mode: {result.fetched_data.get('source', '-')}")
                st.text(f"provider_retry_total: {result.processed_data.get('provider_retry_total', 0)}")

            with st.expander("查看熔断状态"):
                st.json(result.processed_data.get("provider_circuit_state", {}))


if __name__ == '__main__':
    main()

























