#!/bin/bash
OUT="/opt/birdbox/birdbox_full_context.md"
echo "# Birdbox Bioacoustic Lakehouse: Full System Dump" > $OUT
echo "Generated at: $(date)" >> $OUT

echo -e "\n## 1. System Architecture & Node Network" >> $OUT
echo "- **Edge Node (Pi 4)**: \`10.0.0.233\` (Hostname: birdedge)" >> $OUT
echo "- **Compute Hub (M720q)**: \`10.0.0.25\` (Hostname: birdbox)" >> $OUT

echo -e "\n## 2. Active Bronze SQLite Schema" >> $OUT
python3 -c "import sqlite3; con=sqlite3.connect('/opt/birdbox/data/bronze/birdnet.db'); print('Rows:', con.execute('SELECT COUNT(*) FROM detections;').fetchone()[0]); con.close()" >> $OUT 2>&1

echo -e "\n## 3. dbt Configuration (profiles.yml)" >> $OUT
echo '```yaml' >> $OUT
cat /opt/birdbox/dbt-project/profiles.yml 2>/dev/null || cat ~/.dbt/profiles.yml 2>/dev/null >> $OUT
echo '```' >> $OUT

echo -e "\n## 4. dbt Models" >> $OUT
for f in $(find /opt/birdbox/dbt-project/models -name "*.sql" -o -name "*.yml"); do
  echo -e "\n### Model: $f" >> $OUT
  echo '```sql' >> $OUT
  cat "$f" >> $OUT
  echo '```' >> $OUT
done

echo -e "\n## 5. Evidence Source Configurations" >> $OUT
for f in $(find /opt/birdbox/field-journal/sources -name "*.yaml" -o -name "*.json"); do
  echo -e "\n### Source Config: $f" >> $OUT
  echo '```yaml' >> $OUT
  cat "$f" >> $OUT
  echo '```' >> $OUT
done

echo -e "\n## 6. Evidence Dashboard Page Templates" >> $OUT
for f in $(find /opt/birdbox/field-journal/pages -name "*.md" -o -name "*.svelte" 2>/dev/null); do
  echo -e "\n### Page: $f" >> $OUT
  echo '```markdown' >> $OUT
  cat "$f" >> $OUT
  echo '```' >> $OUT
done

echo "Context file generated at: $OUT"
