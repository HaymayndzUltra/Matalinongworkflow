# YAML Front-Matter Scraper

A high-performance web scraper that finds YAML front-matter blocks containing both `description:` and `alwaysApply:` fields, then saves them as `.mdc` files.

## Features

- **Async crawling**: High-performance concurrent web scraping
- **Smart extraction**: Targets code blocks and content areas likely to contain YAML
- **Deduplication**: Automatically removes duplicate YAML blocks using SHA256 hashing
- **Flexible filtering**: Include/exclude URLs based on patterns
- **Rate limiting**: Configurable concurrency and timeout settings
- **Portable**: Works on any system with Python 3.10+

## Installation

```bash
pip install -r requirements.txt
```

## Usage Examples

### Basic crawling from a start URL:
```bash
python3 scrape_yaml_blocks.py --start https://cursor.directory --include cursor.directory --max-pages 100 --out rules_out
```

### Crawl from a list of URLs:
```bash
python3 scrape_yaml_blocks.py --urls urls.txt --out rules_out
```

### Advanced crawling with filters:
```bash
python3 scrape_yaml_blocks.py \
  --start https://example.com \
  --include example.com docs.example.com \
  --exclude admin.example.com api.example.com \
  --max-pages 500 \
  --concurrency 16 \
  --timeout 30 \
  --out extracted_rules
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--start URL` | Starting URL to crawl | Required (or use `--urls`) |
| `--urls FILE` | File with one URL per line | Required (or use `--start`) |
| `--include PATTERN` | Only crawl URLs containing these patterns | All URLs |
| `--exclude PATTERN` | Skip URLs containing these patterns | None |
| `--max-pages N` | Maximum pages to scan | 200 |
| `--concurrency N` | Number of concurrent requests | 8 |
| `--timeout N` | Request timeout in seconds | 20 |
| `--out DIR` | Output directory for .mdc files | `rules_out` |

## Output

- Creates the specified output directory if it doesn't exist
- Saves each unique YAML block as `rule_{hash}.mdc`
- Each file contains the complete YAML block wrapped in `---` markers
- Provides summary statistics after completion

## How It Works

1. **URL Discovery**: Starts from seed URLs and follows links recursively
2. **Content Extraction**: Focuses on code blocks, articles, and main content areas
3. **YAML Detection**: Uses regex to find blocks with both `description:` and `alwaysApply:`
4. **Deduplication**: SHA256 hashing prevents duplicate saves
5. **Concurrent Processing**: Multiple worker threads for high throughput

## Performance Tips

- Use `--concurrency 16-32` for high-bandwidth connections
- Set `--max-pages` based on your target site size
- Use `--include` to focus crawling on relevant domains
- Monitor memory usage for very large sites

## Error Handling

- Gracefully handles network timeouts and connection errors
- Skips non-HTML content automatically
- Continues crawling even if individual pages fail
- Provides detailed progress and summary information

## License

This script is provided as-is for educational and research purposes. Please respect website terms of service and robots.txt files when crawling.
