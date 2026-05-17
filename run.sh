#!/bin/bash

set -euo pipefail

export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-$LANG}"

# 本地测试脚本 / Local testing script
# 主要工作流已迁移到 GitHub Actions (.github/workflows/run.yml)
# Main workflow has been migrated to GitHub Actions (.github/workflows/run.yml)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

load_env_file() {
    local env_file="$1"
    local line key value

    [ -f "$env_file" ] || return 0

    while IFS= read -r line || [ -n "$line" ]; do
        if [[ -z "${line//[[:space:]]/}" || "$line" =~ ^[[:space:]]*# ]]; then
            continue
        fi
        if [[ "$line" != *=* ]]; then
            continue
        fi

        key="${line%%=*}"
        value="${line#*=}"

        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"

        if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
            value="${value:1:${#value}-2}"
        fi

        export "$key=$value"
    done < "$env_file"
}

if [ -f ".env" ]; then
    load_env_file ".env"
fi

RUN_WITH_UV=false

if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
elif command -v uv >/dev/null 2>&1; then
    RUN_WITH_UV=true
fi

run_python() {
    if [ "$RUN_WITH_UV" = "true" ]; then
        uv run --python 3.12 python "$@"
    elif command -v python >/dev/null 2>&1; then
        python "$@"
    else
        python3 "$@"
    fi
}

mkdir -p data assets

# 环境变量检查和提示 / Environment variables check and prompt
echo "=== 本地调试环境检查 / Local Debug Environment Check ==="
if [ -z "${TOKEN_GITHUB:-}" ]; then
    echo "⚠️  提示：未设置 TOKEN_GITHUB / Warning: TOKEN_GITHUB not set"
    echo "可能导致 GitHub 相关功能受限 / May limit GitHub related functionalities"
else
    echo "✅ TOKEN_GITHUB 已设置 / TOKEN_GITHUB is set"
fi

# 检查必需的环境变量 / Check required environment variables
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "⚠️  提示：未设置 OPENAI_API_KEY / Warning: OPENAI_API_KEY not set"
    echo "📝 要进行完整本地调试，请设置以下环境变量 / For complete local debugging, please set the following environment variables:"
    echo ""
    echo "🔑 必需变量 / Required variables:"
    echo "   export OPENAI_API_KEY=\"your-api-key-here\""
    echo ""
    echo "🔧 可选变量 / Optional variables:"
    echo "   export OPENAI_BASE_URL=\"https://api.openai.com/v1\"  # API基础URL / API base URL"
    echo "   export LANGUAGE=\"Chinese\"                           # 语言设置 / Language setting"
    echo "   export CATEGORIES=\"cs.CV, cs.CL\"                    # 关注分类 / Categories of interest"
    echo "   export MODEL_NAME=\"gpt-4o-mini\"                     # 模型名称 / Model name"
    echo ""
    echo "💡 设置后重新运行此脚本即可进行完整测试 / After setting, rerun this script for complete testing"
    echo "🚀 或者继续运行部分流程（爬取+去重检查）/ Or continue with partial workflow (crawl + dedup check)"
    echo ""
    read -r -p "继续部分流程？(y/N) / Continue with partial workflow? (y/N): " continue_partial
    if [[ ! $continue_partial =~ ^[Yy]$ ]]; then
        echo "退出脚本 / Exiting script"
        exit 0
    fi
    PARTIAL_MODE=true
else
    echo "✅ OPENAI_API_KEY 已设置 / OPENAI_API_KEY is set"
    PARTIAL_MODE=false

    # 设置默认值 / Set default values
    export LANGUAGE="${LANGUAGE:-Chinese}"
    export CATEGORIES="${CATEGORIES:-cs.CV, cs.CL}"
    export MODEL_NAME="${MODEL_NAME:-gpt-4o-mini}"
    export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"

    echo "🔧 当前配置 / Current configuration:"
    echo "   LANGUAGE: $LANGUAGE"
    echo "   CATEGORIES: $CATEGORIES"
    echo "   MODEL_NAME: $MODEL_NAME"
    echo "   OPENAI_BASE_URL: $OPENAI_BASE_URL"
fi

echo ""
echo "=== 开始本地调试流程 / Starting Local Debug Workflow ==="

# 获取当前本地日期 / Get current local date
# Local runs should use the same date basis as check_stats.py to avoid
# generating yesterday's filename after midnight in non-UTC timezones.
today=$(date "+%Y-%m-%d")

echo "本地测试：爬取 $today 的arXiv论文... / Local test: Crawling $today arXiv papers..."

# 第一步：流式爬取和持久化 / Step 1: Streaming crawl and persistence
echo "步骤1：开始流式爬取... / Step 1: Starting streaming crawl..."
echo "📝 已有文件会被复用并续跑，不会删除 / Existing files will be reused for resume, not deleted"

done_file=".tmp/enhancer-${today}.done"
enhancer_pid=""
rm -f "$done_file"
mkdir -p ".tmp"

cleanup_enhancer() {
    if [ -n "$enhancer_pid" ] && kill -0 "$enhancer_pid" 2>/dev/null; then
        touch "$done_file"
        wait "$enhancer_pid" || true
    fi
}
trap cleanup_enhancer EXIT

if [ "$PARTIAL_MODE" = "false" ]; then
    echo "启动AI增强队列... / Starting AI enhancement queue..."
    run_python "ai/watch_enhance.py" \
        --data "data/${today}.jsonl" \
        --done-file "$done_file" \
        --max_workers "${ENHANCE_MAX_WORKERS:-1}" &
    enhancer_pid=$!
fi

cd daily_arxiv
export ARXIV_RUN_DATE="$today"
set +e
run_python -m scrapy crawl arxiv
crawl_exit_code=$?
set -e

cd ..

touch "$done_file"

if [ -n "$enhancer_pid" ]; then
    echo "等待AI增强队列处理剩余论文... / Waiting for AI enhancement queue to drain..."
    set +e
    wait "$enhancer_pid"
    enhancer_exit_code=$?
    set -e
    enhancer_pid=""
else
    enhancer_exit_code=0
fi

trap - EXIT

if [ "$crawl_exit_code" -ne 0 ]; then
    echo "爬取失败 / Crawling failed"
    exit "$crawl_exit_code"
fi

if [ "$enhancer_exit_code" -ne 0 ]; then
    echo "AI增强队列失败 / AI enhancement queue failed"
    exit "$enhancer_exit_code"
fi

if [ ! -s "data/${today}.jsonl" ] && { [ "$PARTIAL_MODE" = "true" ] || [ ! -s "data/${today}_AI_enhanced_${LANGUAGE}.jsonl" ]; }; then
    echo "未生成新的今日数据文件，可能没有新论文 / No new data file generated, possibly no new papers"
    exit 1
fi

if [ "$PARTIAL_MODE" = "false" ]; then
    if [ ! -s "data/${today}_AI_enhanced_${LANGUAGE}.jsonl" ]; then
        echo "AI增强文件为空或不存在，可能没有新论文 / AI enhanced file is empty or missing, possibly no new papers"
        exit 1
    fi
    echo "AI enhancement streaming completed"
else
    echo "Skipping AI processing (partial mode)"
fi

# 第二步：转换为Markdown / Step 2: Convert to Markdown
echo "Step 2: Converting to Markdown..."
cd to_md

if [ "$PARTIAL_MODE" = "false" ] && [ -f "../data/${today}_AI_enhanced_${LANGUAGE}.jsonl" ]; then
    echo "Using AI enhanced data for conversion..."
    run_python convert.py --data "../data/${today}_AI_enhanced_${LANGUAGE}.jsonl"
    echo "AI enhanced Markdown conversion completed"
else
    if [ "$PARTIAL_MODE" = "true" ]; then
        echo "Skipping Markdown conversion (partial mode, requires AI enhanced data)"
    else
        echo "Error: AI enhanced file not found"
        echo "AI file: ../data/${today}_AI_enhanced_${LANGUAGE}.jsonl"
        exit 1
    fi
fi

cd ..

# 第三步：更新文件列表 / Step 3: Update file list
echo "步骤3：更新文件列表... / Step 3: Updating file list..."
shopt -s nullglob
jsonl_files=(data/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.jsonl)
if [ ${#jsonl_files[@]} -eq 0 ]; then
    : > assets/file-list.txt.tmp
else
    printf '%s\n' "${jsonl_files[@]#data/}" | sort > assets/file-list.txt.tmp
fi
mv assets/file-list.txt.tmp assets/file-list.txt
shopt -u nullglob
echo "✅ 文件列表更新完成 / File list updated"

# 完成总结 / Completion summary
echo ""
echo "=== 本地调试完成 / Local Debug Completed ==="
if [ "$PARTIAL_MODE" = "false" ]; then
    echo "🎉 完整流程已完成 / Complete workflow finished:"
    echo "   ✅ 流式数据爬取 / Streaming data crawling"
    echo "   ✅ 续跑去重 / Resume-aware deduplication"
    echo "   ✅ 流式AI增强 / Streaming AI enhancement"
    echo "   ✅ Markdown转换 / Markdown conversion"
    echo "   ✅ 文件列表更新 / File list update"
else
    echo "🔄 部分流程已完成 / Partial workflow finished:"
    echo "   ✅ 流式数据爬取 / Streaming data crawling"
    echo "   ✅ 续跑去重 / Resume-aware deduplication"
    echo "   ⏭️  跳过AI增强和Markdown转换 / Skipped AI enhancement and Markdown conversion"
    echo "   ✅ 文件列表更新 / File list update"
    echo ""
    echo "💡 提示：设置OPENAI_API_KEY可启用完整功能 / Tip: Set OPENAI_API_KEY to enable full functionality"
fi