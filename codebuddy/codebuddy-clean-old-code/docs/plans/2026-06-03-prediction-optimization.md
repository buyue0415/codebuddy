# 智能预测模块深度优化 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对现有基于规则的投票预测系统进行 ML 增强，目标方向准确率从 58-65% 提升至 65-75%

**Architecture:** 保留现有规则引擎作为基础，新增 RandomForest 方向分类器 + Ridge 涨跌幅回归的混合模型，整合数据质量保障管道

**Tech Stack:** Python 3, scikit-learn, pandas, numpy, sqlite3, 现有 sync_all.py 架构

---

### Task 1: 数据质量分析脚本

**Files:**
- Create: `scripts/optimize_predict.py` (主优化脚本)

**功能：**
- 从 SQLite 加载所有自选股 K 线数据
- 分析特征分布（均值/标准差/偏度/峰度）
- 检测缺失值、异常值（3σ + IQR 双判据）
- 生成可视化报告

### Task 2: 增强特征工程

**Files:**
- Modify: `scripts/optimize_predict.py` (扩展)

**新增 13 项衍生特征：**
- 趋势类：MA5_20_ratio, ADX, 通道位置
- 波动类：ATR_pct, 历史波动率, 高低振幅比
- 统计类：Z-score, 偏度, 峰度, 涨跌连续性
- 交叉类：MACD_RSI, BB_KDJ
- 时序类：volume_ma_ratio, change_accel

### Task 3: ML 模型训练与评估

**Files:**
- Modify: `scripts/optimize_predict.py` (扩展)

**模型：**
- RandomForestClassifier (方向预测)
- Ridge CV (涨跌幅回归)
- TimeSeriesSplit (5折时序交叉验证)
- 特征重要性分析

### Task 4: 集成到 sync_all.py

**Files:**
- Modify: `scripts/sync_all.py` (新增 ML 预测函数)
- Modify: `scripts/db_helper.py` (新增 ml_model 表读写)

**集成方式：**
- Step 5.5: ML 模型训练/更新
- Step 6: 预测时优先使用 ML 预测，规则投票作为后备
- 新增 ml_models 表存储训练好的模型参数
