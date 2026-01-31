# Palateful Production Hosting Costs

## Executive Summary

This document analyzes the production hosting costs for Palateful, a kitchen management app with AI-powered recipe and ingredient features.

**Current Status:**
- OCR Batch infrastructure deployed via Terraform (GPU processing with Spot instances)
- Full production stack (API, database, cache) not yet deployed

**Monthly Cost Ranges by Phase:**
| Phase | Users | Monthly Cost |
|-------|-------|--------------|
| MVP | ~100 | $110-160 |
| Growth | ~1,000 | $250-520 |
| Scale | ~10,000 | $750-2,000 |

---

## Infrastructure Costs

### Currently Deployed (Terraform)

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| VPC + Networking | $0 | No data transfer charges at low volume |
| AWS Batch (GPU OCR) | $0-50 | Spot instances, scales to zero when idle |
| S3 Buckets | $1-20 | Storage + requests |
| ECR Repository | $1-5 | Container image storage |
| CloudWatch Logs | $2-10 | Log ingestion + storage |
| **Subtotal** | **$4-85** | Variable based on usage |

### Required for Production (Not Yet Deployed)

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| RDS PostgreSQL (db.t4g.micro) | $13-25 | Or Aurora Serverless v2 |
| ElastiCache Redis (cache.t4g.micro) | $12-25 | Or serverless alternative |
| ECS Fargate (API) | $25-80 | 0.25-1 vCPU, 0.5-2GB RAM |
| Application Load Balancer | $18-30 | $0.0225/hour + LCU charges |
| API Gateway (optional) | $0-15 | Only if using HTTP API |
| Route 53 | $0.50 | Hosted zone |
| ACM Certificates | $0 | Free with AWS |
| **Subtotal** | **$69-175** | Baseline infrastructure |

---

## AI Feature Costs

### OpenAI (gpt-4o-mini)

| Metric | Cost |
|--------|------|
| Input tokens | $0.15 / 1M tokens |
| Output tokens | $0.60 / 1M tokens |
| Cached input tokens | $0.075 / 1M tokens |

**Per-Operation Estimates:**
| Operation | Tokens (In/Out) | Cost |
|-----------|-----------------|------|
| Recipe extraction | ~2,000 / 1,500 | $0.001-0.004 |
| Chat turn (simple) | ~500 / 300 | $0.0003 |
| Chat turn (complex) | ~2,000 / 1,000 | $0.001-0.003 |
| Ingredient parsing | ~300 / 200 | $0.0002 |

### HunyuanOCR (Self-hosted on AWS Batch)

| State | Cost |
|-------|------|
| Idle | $0 (scales to zero) |
| Per image (Spot GPU) | ~$0.001 |
| Per image (On-demand GPU) | ~$0.01 |

**Comparison to Cloud OCR APIs:**
| Service | Per Image | Savings with Self-hosted |
|---------|-----------|--------------------------|
| Google Cloud Vision | $0.015 | 15x cheaper |
| AWS Textract | $0.015 | 15x cheaper |
| Azure Computer Vision | $0.01 | 10x cheaper |

---

## Cost Breakdown by Unit

### Per User (Monthly)

| Component | Light User | Moderate User | Heavy User |
|-----------|------------|---------------|------------|
| DB storage (10-500MB) | $0.002 | $0.01 | $0.05 |
| API compute | $0.30 | $0.50 | $1.00 |
| AI chat (5-50 turns) | $0.006 | $0.03 | $0.06 |
| OCR (5-50 images) | $0.005 | $0.02 | $0.05 |
| Recipe AI (2-20 recipes) | $0.004 | $0.02 | $0.08 |
| **Total** | **~$0.32** | **~$0.58** | **~$1.24** |

### Per Operation

| Operation | Cost |
|-----------|------|
| Recipe extraction (AI) | $0.001-0.004 |
| OCR processing (Spot GPU) | ~$0.001 |
| Chat message (simple) | ~$0.0003 |
| Chat message (complex) | ~$0.001-0.003 |
| Ingredient parsing | ~$0.0002 |

### Fixed Weekly Costs

| Component | Weekly Cost |
|-----------|-------------|
| RDS/Aurora baseline | $3-6 |
| ElastiCache/Redis baseline | $3-6 |
| ECS Fargate (always-on) | $6-20 |
| Load Balancer | $4-8 |
| Monitoring/Logs | $0.50-2 |
| **Total** | **$17-42** |

---

## Grand Total Estimates

### By User Scale

| Phase | Users | Fixed Costs | Variable Costs | Total Monthly |
|-------|-------|-------------|----------------|---------------|
| MVP | 100 | $75-130 | $35-60 | **$110-160** |
| Growth | 1,000 | $100-180 | $150-340 | **$250-520** |
| Scale | 10,000 | $200-400 | $550-1,600 | **$750-2,000** |

### Per-User Cost at Scale

| Scale | Per-User Monthly |
|-------|------------------|
| 100 users | $1.10-1.60 |
| 1,000 users | $0.25-0.52 |
| 10,000 users | $0.08-0.20 |

---

## Cost Reduction Strategies

### A. Database: Aurora Serverless v2

**Overview:**
Aurora Serverless v2 uses Aurora Capacity Units (ACUs) that scale automatically based on demand.

| Metric | Value |
|--------|-------|
| Minimum ACU | 0.5 |
| Cost per ACU-hour | $0.12 |
| Storage | $0.10/GB/month |

**Cost Comparison:**

| Scenario | RDS db.t4g.micro | Aurora Serverless v2 |
|----------|------------------|----------------------|
| Always idle | $13/month | $44/month (0.5 ACU) |
| Light usage (8h/day active) | $13/month | $29/month |
| Variable spikes | $13-25/month | $44-120/month |
| Pause-capable | No | Yes (manual) |

**Recommendation:**
- For **predictable, low traffic**: RDS db.t4g.micro is cheaper
- For **variable/spiky traffic**: Aurora Serverless v2 handles bursts better
- Aurora supports auto-pause in v1 but not v2; v2 requires 0.5 ACU minimum

### B. Single VPS Approach ($20-50/month)

Run everything on one machine for maximum cost efficiency at low scale.

**Provider Options:**
| Provider | Specs | Monthly Cost |
|----------|-------|--------------|
| Hetzner CX32 | 4 vCPU, 8GB RAM, 80GB | $7.50 |
| Hetzner CX42 | 8 vCPU, 16GB RAM, 160GB | $15 |
| DigitalOcean | 4 vCPU, 8GB RAM | $48 |
| Linode | 4 vCPU, 8GB RAM | $36 |

**What runs on VPS:**
- PostgreSQL with pgvector
- Redis
- FastAPI application
- Nginx reverse proxy

**Pros:**
- Dramatically cheaper ($20-50 vs $110-175)
- Simple deployment
- Full control

**Cons:**
- No auto-scaling
- Manual backups needed
- Single point of failure
- GPU OCR still needs cloud (or Modal.com)

### C. Serverless/Managed Stack ($30-80/month)

Mix free tiers and pay-as-you-go services.

| Component | Service | Monthly Cost |
|-----------|---------|--------------|
| Database | Neon.tech (free: 0.5GB) | $0-19 |
| Cache | Upstash Redis (free: 10K/day) | $0-10 |
| API Hosting | Railway.app | $5-20 |
| GPU OCR | Modal.com | $10-30 |
| CDN | Cloudflare (free) | $0 |
| **Total** | | **$15-79** |

**Free Tier Limits:**
- Neon: 0.5GB storage, 1 project, 100 compute hours
- Upstash: 10,000 commands/day
- Railway: $5 free credit, then usage-based
- Modal: $30/month free compute credit

### D. Self-Hosted LLM (Long-term)

Replace OpenAI with self-hosted Llama for high-volume operations.

**Options:**
| Setup | Hardware | Monthly Cost | Capability |
|-------|----------|--------------|------------|
| Modal.com | A10G GPU on-demand | $0.76/hour | Llama 3.1 8B |
| Hetzner GPU | RTX 4090 dedicated | ~$200/month | Llama 3.1 70B |
| Lambda Labs | A10 | ~$0.75/hour | Llama 3.1 8B |

**Break-even Analysis:**
- At $200/month for GPU server
- Replaces ~$200 worth of OpenAI tokens
- Break-even: ~50,000 recipe extractions/month
- Better suited for 10,000+ active users

**Recommendation:** Not cost-effective until significant scale; OpenAI is cheaper for MVP/Growth phases.

---

## Recommended Path

### Phase 1: MVP ($25-50/month)

Optimized for minimal cost while validating product-market fit.

| Component | Solution | Cost |
|-----------|----------|------|
| Compute | Hetzner VPS (CX32) | $7.50 |
| Database | PostgreSQL on VPS | $0 |
| Cache | Redis on VPS | $0 |
| AI/LLM | OpenAI pay-as-you-go | $10-30 |
| OCR | Modal.com or keep AWS Batch | $5-10 |
| CDN/SSL | Cloudflare (free) | $0 |
| **Total** | | **$22-47** |

**Tradeoffs:**
- Manual deployment and updates
- Need backup strategy (pg_dump to S3)
- Limited to VPS capacity (~500 concurrent users max)

### Phase 2: Growth ($80-150/month)

When you need reliability and scaling.

| Component | Solution | Cost |
|-----------|----------|------|
| Database | Aurora Serverless v2 or Neon Pro | $44-80 |
| Cache | Upstash or ElastiCache | $10-25 |
| Compute | Railway or ECS Fargate | $20-40 |
| AI/LLM | OpenAI | $20-50 |
| OCR | AWS Batch (Spot) | $10-30 |
| CDN | Cloudflare | $0 |
| **Total** | | **$104-225** |

### Phase 3: Scale ($200-500/month self-hosted AI)

When AI costs become dominant.

| Component | Solution | Cost |
|-----------|----------|------|
| Infrastructure | AWS managed services | $150-300 |
| AI/LLM | Self-hosted Llama on GPU | $50-200 |
| OCR | Self-hosted on same GPU | Included |
| **Total** | | **$200-500** |

---

## Cost Monitoring Recommendations

### AWS Budget Alerts

Set up alerts at:
- 50% of expected monthly spend
- 80% of expected monthly spend
- 100% of expected monthly spend

### Key Metrics to Track

| Metric | Why |
|--------|-----|
| OpenAI token usage | Largest variable cost |
| GPU compute hours | OCR costs |
| Database IOPS | Can spike unexpectedly |
| Data transfer | Watch for egress charges |
| API request count | Correlates with all costs |

### Cost Allocation Tags

Tag all resources with:
- `environment`: dev/staging/prod
- `service`: api/worker/ocr/migrator
- `cost-center`: infrastructure/ai/storage

---

## Summary

| Scenario | Monthly Cost | Best For |
|----------|--------------|----------|
| **Absolute Minimum** | $25-40 | Side project, validation |
| **MVP on AWS** | $110-160 | Serious launch, 100 users |
| **Growth Phase** | $250-520 | 1,000 active users |
| **Scale Phase** | $750-2,000 | 10,000+ users |

**Key Insights:**
1. Fixed infrastructure costs dominate at low scale ($70-130/month baseline)
2. AI costs (OpenAI) become dominant only at 1,000+ active users
3. Self-hosted OCR is 10-30x cheaper than cloud OCR APIs
4. Single VPS can reduce costs by 60-70% at MVP scale
5. Aurora Serverless v2 is better for spiky workloads, not steady low traffic
6. Self-hosted LLM only makes sense at 10,000+ users
