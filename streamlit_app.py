"""
Streamlit UI for Document Analyzer.
Provides a user-friendly interface for document upload and analysis.
"""
import streamlit as st
import os
import json
from pathlib import Path
import time

from app.config import settings
from app.analyzer import DocumentAnalyzer
from app.report_generator import ReportGenerator

# Page configuration
st.set_page_config(
    page_title="Document Analyzer",
    page_icon="📄",
    layout="wide"
)

# Initialize session state
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'report' not in st.session_state:
    st.session_state.report = None
if 'report_paths' not in st.session_state:
    st.session_state.report_paths = {}


def progress_callback(message: str, progress: int):
    """Callback for progress updates."""
    st.session_state.progress_message = message
    st.session_state.progress_value = progress


def main():
    """Main Streamlit application."""
    
    st.title("📄 Анализатор документов")
    st.markdown("Загрузите Word-документ и получите детальный анализ с помощью AI")
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        st.info(f"**LLM Provider:** {settings.llm_provider}")
        st.info(f"**Model:** {settings.openai_model if settings.llm_provider == 'openai' else settings.anthropic_model}")
        st.info(f"**Chunk Size:** {settings.chunk_size} tokens")
        
        st.markdown("---")
        st.markdown("### О приложении")
        st.markdown("""
        Это приложение анализирует большие Word-документы:
        - Разбивает документ на части
        - Анализирует каждую часть через LLM
        - Находит проблемы и несоответствия
        - Генерирует детальный отчёт
        """)
    
    # Main content
    tab1, tab2 = st.tabs(["📤 Загрузка и анализ", "📊 Результаты"])
    
    with tab1:
        st.header("Загрузите документ")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Выберите .docx файл",
            type=['docx'],
            help=f"Максимальный размер: {settings.max_file_size_mb}MB"
        )
        
        # Instructions input
        instructions = st.text_area(
            "Инструкции для анализа",
            placeholder="Например: Проверь документ на грамматические ошибки, логические несоответствия и соответствие научному стилю изложения.",
            height=150,
            help="Опишите, что именно нужно проверить в документе"
        )
        
        # Analyze button
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            analyze_button = st.button("🚀 Анализировать", type="primary", disabled=not uploaded_file or not instructions)
        
        # Analysis process
        if analyze_button and uploaded_file and instructions:
            # Save uploaded file
            upload_dir = Path(settings.upload_dir)
            upload_dir.mkdir(exist_ok=True)
            
            file_path = upload_dir / uploaded_file.name
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Initialize analyzer
                analyzer = DocumentAnalyzer(str(file_path))
                
                # Custom progress callback
                def update_progress(message, progress):
                    status_text.text(message)
                    progress_bar.progress(progress / 100)
                
                # Perform analysis
                with st.spinner("Анализ в процессе..."):
                    report = analyzer.analyze(instructions, progress_callback=update_progress)
                
                # Store in session state
                st.session_state.report = report
                st.session_state.analysis_complete = True
                
                # Generate reports
                generator = ReportGenerator(report)
                st.session_state.report_paths = {
                    'json': generator.generate_json(),
                    'docx': generator.generate_docx(),
                    'html': generator.generate_html()
                }
                
                progress_bar.progress(100)
                status_text.text("✅ Анализ завершён!")
                
                st.success("🎉 Анализ успешно завершён! Перейдите на вкладку 'Результаты'")
                
                # Auto-switch to results tab
                time.sleep(1)
                
            except Exception as e:
                st.error(f"❌ Ошибка при анализе: {str(e)}")
                st.exception(e)
    
    with tab2:
        if not st.session_state.analysis_complete or not st.session_state.report:
            st.info("📋 Загрузите и проанализируйте документ на вкладке 'Загрузка и анализ'")
            return
        
        report = st.session_state.report
        
        # Summary metrics
        st.header("📊 Общая статистика")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Документ", report.document_name)
        with col2:
            st.metric("Частей", report.total_chunks)
        with col3:
            st.metric("Всего проблем", report.total_findings)
        with col4:
            high_count = len(report.get_findings_by_severity('high'))
            st.metric("Высокая", high_count, delta=None, delta_color="inverse")
        with col5:
            medium_count = len(report.get_findings_by_severity('medium'))
            st.metric("Средняя", medium_count)
        
        # Download buttons
        st.header("📥 Скачать отчёты")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'json' in st.session_state.report_paths:
                with open(st.session_state.report_paths['json'], 'rb') as f:
                    st.download_button(
                        label="📄 JSON",
                        data=f,
                        file_name="report.json",
                        mime="application/json"
                    )
        
        with col2:
            if 'docx' in st.session_state.report_paths:
                with open(st.session_state.report_paths['docx'], 'rb') as f:
                    st.download_button(
                        label="📝 DOCX",
                        data=f,
                        file_name="report.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
        
        with col3:
            if 'html' in st.session_state.report_paths:
                with open(st.session_state.report_paths['html'], 'rb') as f:
                    st.download_button(
                        label="🌐 HTML",
                        data=f,
                        file_name="report.html",
                        mime="text/html"
                    )
        
        # Global analysis
        if report.global_analysis:
            st.header("🌍 Глобальный анализ")
            
            with st.expander("📝 Общее резюме", expanded=True):
                st.write(report.global_analysis.overall_summary)
            
            if report.global_analysis.document_structure_issues:
                with st.expander("🏗️ Проблемы структуры"):
                    for issue in report.global_analysis.document_structure_issues:
                        st.markdown(f"- {issue}")
            
            if report.global_analysis.consistency_issues:
                with st.expander("🔄 Проблемы согласованности"):
                    for issue in report.global_analysis.consistency_issues:
                        st.markdown(f"- {issue}")
            
            if report.global_analysis.recommendations:
                with st.expander("💡 Рекомендации"):
                    for rec in report.global_analysis.recommendations:
                        st.markdown(f"- {rec}")
        
        # Findings by severity
        st.header("🔍 Найденные проблемы")
        
        severity_filter = st.selectbox(
            "Фильтр по серьёзности",
            ["Все", "Высокая", "Средняя", "Низкая"]
        )
        
        type_filter = st.selectbox(
            "Фильтр по типу",
            ["Все", "style", "grammar", "structure", "logic", "compliance", "other"]
        )
        
        # Filter findings
        all_findings = []
        for chunk in report.chunk_analyses:
            for finding in chunk.findings:
                all_findings.append({
                    "chunk_id": chunk.chunk_id,
                    "finding": finding
                })
        
        # Apply filters
        filtered_findings = all_findings
        if severity_filter != "Все":
            severity_map = {"Высокая": "high", "Средняя": "medium", "Низкая": "low"}
            filtered_findings = [f for f in filtered_findings if f["finding"].severity == severity_map[severity_filter]]
        
        if type_filter != "Все":
            filtered_findings = [f for f in filtered_findings if f["finding"].issue_type == type_filter]
        
        st.write(f"Показано проблем: {len(filtered_findings)}")
        
        # Display findings
        for item in filtered_findings:
            finding = item["finding"]
            chunk_id = item["chunk_id"]
            
            # Severity color
            severity_colors = {
                "high": "🔴",
                "medium": "🟡",
                "low": "⚪"
            }
            
            with st.expander(f"{severity_colors[finding.severity]} Часть {chunk_id} - {finding.issue_type} ({finding.severity})"):
                st.markdown(f"**Цитата:**")
                st.info(finding.quote)
                
                st.markdown(f"**Проблема:**")
                st.write(finding.problem)
                
                st.markdown(f"**Рекомендация:**")
                st.success(finding.recommendation)
        
        # Detailed chunk analysis
        st.header("📑 Детальный анализ по частям")
        
        for chunk in report.chunk_analyses:
            with st.expander(f"Часть {chunk.chunk_id} ({len(chunk.findings)} проблем)"):
                st.markdown("**Краткое содержание:**")
                st.write(chunk.summary)
                
                if chunk.findings:
                    st.markdown("**Найденные проблемы:**")
                    for i, finding in enumerate(chunk.findings, 1):
                        st.markdown(f"**{i}. [{finding.severity.upper()}] {finding.issue_type}**")
                        st.markdown(f"- Цитата: *{finding.quote}*")
                        st.markdown(f"- Проблема: {finding.problem}")
                        st.markdown(f"- Рекомендация: {finding.recommendation}")
                        st.markdown("---")


if __name__ == "__main__":
    main()
