# MLR Validation Pipeline Architecture

## Overview
The system has **2 main pipelines** with **3 conversion paths** for different document types.

---

## 🔵 PIPELINE 1: Research Papers (Citations/Footnotes)

### Endpoint
```
POST /run-pipeline
```

### Flow
```
PDF Upload
    ↓
extract_footnotes() [Superscript.py]
    ↓
build_validation_dataframe() [conversion.py]
    ↓
validate_statements() [Gemini_version.py]
    ↓
Results (Supported/Contradicted/Not Found)
```

### Use Case
- Academic research papers
- Documents with superscript citations (¹, ², ³)
- General brochure validation with references

### Data Format
- Input: PDF with in-text citations
- Extraction: `{page_number, superscript_number, heading, statement}`
- Conversion: `statement | reference_no | reference`

---

## 🟢 PIPELINE 2: Drug Tables

### Base Endpoint
```
POST /api/drugs/pipeline
```

### Flow
```
PDF Upload
    ↓
extract_drug_superscript_table_data() [Superscript.py]
    ↓
Auto-Detection (IMAGE 1 vs IMAGE 2)
    ↓
┌─────────────────────┬─────────────────────┐
│   IMAGE 1 Path      │   IMAGE 2 Path      │
│   (pH Tables)       │   (Statements)      │
└─────────────────────┴─────────────────────┘
    ↓                         ↓
build_validation_           build_validation_
rows_image1()               rows_image2()
    ↓                         ↓
validate_statement_against_all_papers()
(pharmaceutical mode)
    ↓
Results
```

---

## 📊 IMAGE 1: pH Compatibility Tables

### Endpoint
```
POST /api/drugs/convert/image1
```

### Table Structure
```
┌──────────────┬────────┬───────────┬───────────┬───────────┐
│ Drug Name    │ pH     │ Solution A│ Solution B│ Solution C│
│ (w/ super¹)  │        │    ●      │    ◆      │    ●      │
├──────────────┼────────┼───────────┼───────────┼───────────┤
│ amikacin¹,²  │ 3.5-5.5│    ●      │    ◆      │    ●      │
│ ampicillin³  │ 5.0-7.5│    ●      │           │    ●      │
└──────────────┴────────┴───────────┴───────────┴───────────┘
```

### Extraction Format
```json
{
  "page_number": 1,
  "row_name": "amikacin",
  "superscript_number": "1,2",
  "ph_value": "3.5-5.5",
  "column_name": "Solution A.Solution B.Solution C",
  "mark_type": "●.◆.●"
}
```

### Conversion Output
```
Statement: "amikacin. 3.5-5.5. Solution A. Solution B. Solution C."
Reference No: "1,2"
```

### Use Cases
- Drug compatibility matrices
- pH range tables
- Solution interaction tables
- Multi-column compatibility grids

---

## 📝 IMAGE 2: Statement-Based Tables

### Endpoint
```
POST /api/drugs/convert/image2
```

### Table Structure
```
┌──────────────┬────────────────────────────────┬───────────────┐
│ Drug Name    │ Statement/Instruction          │ Column Header │
│ (w/ super¹)  │ (w/ super²)                    │               │
├──────────────┼────────────────────────────────┼───────────────┤
│ amikacin¹    │ Store in refrigerator²         │ Storage       │
│ ampicillin³  │ Mix with saline only⁴          │ Preparation   │
└──────────────┴────────────────────────────────┴───────────────┘
```

### Extraction Format
```json
{
  "page_number": 1,
  "row_name": "amikacin",
  "row_superscript": "1",
  "statement": "Store in refrigerator",
  "statement_superscript": "2",
  "column_name": "Storage"
}
```

### Conversion Output
```
Statement: "amikacin. Store in refrigerator. Storage."
Reference No: "1" (row_superscript has priority)
```

### Use Cases
- Dosage instructions
- Storage requirements
- Preparation guidelines
- Administration protocols

---

## 🤖 Auto-Detection Logic

### How the System Decides

The `build_validation_rows_special_case()` function checks the first row:

```python
# Detection Order:
1. Check for 'statement' field populated → IMAGE 2
2. Check for 'ph_value' or 'mark_type' → IMAGE 1
3. Default fallback → IMAGE 1
```

### Manual Override

If auto-detection fails, use explicit endpoints:

```bash
# Force IMAGE 1 (pH compatibility)
POST /api/drugs/convert/image1

# Force IMAGE 2 (statement-based)
POST /api/drugs/convert/image2

# Auto-detect (default)
POST /api/drugs/convert
```

---

## 🔄 Complete Drug Pipeline Endpoints

```
┌─────────────────────────────────────────────────┐
│        Drug Validation Pipeline                 │
└─────────────────────────────────────────────────┘

1. Extract
   POST /api/drugs/extract
   → Upload PDF → Returns raw JSON records

2. Convert (Choose One)
   a) POST /api/drugs/convert          [Auto-detect]
   b) POST /api/drugs/convert/image1   [pH tables]
   c) POST /api/drugs/convert/image2   [Statements]
   → Send records → Returns validation rows

3. Validate
   POST /api/drugs/validate
   → Send statement + references → Returns validation

4. Full Pipeline
   POST /api/drugs/pipeline
   → Upload PDF + references → Returns complete results
```

---

## 📋 Summary Table

| Pipeline | Endpoint | Extraction | Conversion | Validation Mode |
|----------|----------|------------|------------|-----------------|
| **Research** | `/run-pipeline` | `extract_footnotes()` | `build_validation_dataframe()` | `research` |
| **Drug (Auto)** | `/api/drugs/pipeline` | `extract_drug_superscript_table_data()` | `build_validation_rows_special_case()` | `pharmaceutical` |
| **Drug IMAGE 1** | `/api/drugs/convert/image1` | `extract_drug_superscript_table_data()` | `build_validation_rows_image1()` | `pharmaceutical` |
| **Drug IMAGE 2** | `/api/drugs/convert/image2` | `extract_drug_superscript_table_data()` | `build_validation_rows_image2()` | `pharmaceutical` |

---

## 🎯 When to Use What

### Use Research Pipeline When:
- Document has traditional citations (superscript numbers)
- References listed at the end
- Academic/scientific papers
- Brochures with citation-based claims

### Use Drug Pipeline (Auto) When:
- Drug compatibility tables
- Mixed table types in same PDF
- Unsure which IMAGE type to use

### Use IMAGE 1 Explicitly When:
- pH compatibility matrices
- Multi-column comparison tables
- Circle/diamond mark indicators
- Need precise pH + columns format

### Use IMAGE 2 Explicitly When:
- Dosage/instruction tables
- Single statement per row
- Two-column format (drug + instruction)
- Auto-detect gives wrong format

---

## 🐛 Troubleshooting

### Problem: Wrong Statement Format
**Solution**: Use explicit IMAGE 1 or IMAGE 2 endpoint instead of auto-detect

### Problem: "amikacin. Drug. amikacin..."
**Cause**: Auto-detect chose wrong path
**Solution**: Use `/api/drugs/convert/image1` or `/image2` explicitly

### Problem: Missing pH Values
**Check**: Ensure extraction captured `ph_value` field
**Fix**: Verify PDF table has pH column, or use IMAGE 2 if not applicable

---

## 🔧 Configuration Files

- **Extraction**: `Superscript.py`
- **Conversion**: `conversion.py`
- **Validation**: `Gemini_version.py`
- **API Routes**: `validation_api.py`
- **Main App**: `app.py`
