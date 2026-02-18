---
name: research-arxiv
description: Research latest AI/ML papers from ArXiv
tags: [research, arxiv, papers]
---

# ArXiv Research Skill

Research and analyze the latest AI/ML papers from ArXiv.

## Workflow

1. **Fetch RSS Feed**
   - URL: http://export.arxiv.org/rss/cs.AI
   - Parse using feedparser library
   - Extract entries from the last hour

2. **Parse Each Entry**
   - Extract: title, authors, abstract, PDF URL, arXiv ID
   - Parse published timestamp
   - Clean and normalize data

3. **Score Relevance** (1-10 scale)
   - Base score: 5
   - +2 for high-impact topics: LLMs, transformers, diffusion, multimodal, agents
   - +1 for code releases, implementations, benchmarks
   - +1 for novel/breakthrough claims
   - +1 for technical depth (architecture, training, optimization)
   - -1 for purely theoretical work
   - Final score clamped to 1-10

4. **Filter Items**
   - Keep only items from last hour
   - Keep only items with relevance score >= 5
   - Skip duplicates (check database using content fingerprints)

5. **Return Top Results**
   - Sort by relevance score (descending)
   - Return top 5 papers
   - Format as JSON for easy parsing

## Output Format

Return JSON array with this structure:

```json
[
  {
    "title": "Paper Title",
    "url": "https://arxiv.org/abs/XXXX.XXXXX",
    "pdf_url": "https://arxiv.org/pdf/XXXX.XXXXX.pdf",
    "arxiv_id": "XXXX.XXXXX",
    "authors": ["Author 1", "Author 2"],
    "summary": "Brief abstract summary...",
    "relevance_score": 8,
    "category": "research",
    "source": "arxiv",
    "published_date": "2026-02-15T10:30:00"
  }
]
```

## Scoring Criteria

### High Priority (8-10 points)
- Novel LLM architectures or training methods
- Multimodal models (vision-language, audio-language)
- Agent architectures and reasoning systems
- State-of-the-art results on major benchmarks
- Code releases with practical applications

### Medium Priority (6-7 points)
- Improvements to existing methods
- New datasets or benchmarks
- Application papers with real-world impact
- Optimization techniques
- Fine-tuning and alignment methods

### Low Priority (4-5 points)
- Incremental improvements
- Survey papers
- Theoretical analysis
- Narrow applications
- Purely mathematical proofs

## Error Handling

- If RSS feed is unavailable, retry up to 3 times with exponential backoff
- If parsing fails for an entry, log warning and continue with next entry
- If no items pass the filter, return empty array (not an error)
- Always return valid JSON even if empty

## Usage Example

This skill is called by the content-researcher subagent when researching ArXiv sources.
