# Bioinformatics Workflow Platform - Project Overview

## 🎯 What You Have

A **production-ready Flask web application** designed to run your 4 bioinformatics analysis scripts as an integrated pipeline behind Nginx + Gunicorn. This is NOT a toy example - it's a fully-functional, secure, scalable platform ready for deployment.

## 📋 Key Features

### ✅ Complete Backend Infrastructure
- **User Authentication System**: Secure registration, login, logout with bcrypt password hashing
- **Database Models**: User → Project → Experiment hierarchy with SQLAlchemy ORM
- **RESTful API**: Complete CRUD operations for projects and experiments
- **Session Management**: Secure session-based authentication with Flask-Login
- **File Upload Handling**: Secure multi-file upload with validation and per-user isolation
- **Asynchronous Task Queue**: Celery + Redis for non-blocking pipeline execution
- **Result Management**: Store and serve final contingency tables

### ✅ Bioinformatics Pipeline Integration
- **Modular Pipeline Service**: Clean integration points for your 4 scripts
- **Sequential Execution**: Script 1 (DEA) → Script 2 (VEP) → Script 3 (Join) → Script 4 (Contingency)
- **Progress Tracking**: Real-time status updates (queued, running, completed, failed)
- **Error Handling**: Comprehensive error capture and reporting
- **File Management**: Automatic directory structure and file path management
- **Intermediate Storage**: Separate storage for temporary and final results

### ✅ Production Deployment Ready
- **Gunicorn WSGI Server**: Multi-worker production server configuration
- **Nginx Reverse Proxy**: Complete configuration with SSL/HTTPS support
- **Systemd Services**: Service files for Gunicorn and Celery workers
- **Security Hardening**: CSRF protection, secure headers, permission isolation
- **Logging System**: Comprehensive logging with rotation
- **Database Migrations**: Flask-Migrate for schema versioning

### ✅ Developer Experience
- **Extensive Documentation**: README, API docs, deployment guide, script integration guide
- **Example Scripts**: Template scripts showing exactly how to integrate your code
- **Clear Error Messages**: Helpful validation and error reporting
- **Modular Architecture**: Clean separation of concerns (models, services, routes, utilities)

## 🏗️ Architecture

```
┌─────────────┐
│   Nginx     │ ← Reverse proxy, SSL termination, static files
└──────┬──────┘
       │
┌──────▼──────┐
│  Gunicorn   │ ← WSGI server (multiple workers)
└──────┬──────┘
       │
┌──────▼──────────────────────────────────────────────┐
│                Flask Application                      │
│  ┌────────────┬────────────┬────────────────────┐  │
│  │   Auth     │  Projects  │   Experiments      │  │
│  │ Blueprint  │ Blueprint  │    Blueprint       │  │
│  └────────────┴────────────┴────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │            Services Layer                    │  │
│  │  • Pipeline Service (YOUR SCRIPTS HERE)     │  │
│  │  • File Handling Service                    │  │
│  │  • Celery Tasks                            │  │
│  └─────────────────────────────────────────────┘  │
└───────────┬──────────────────────┬─────────────────┘
            │                      │
   ┌────────▼────────┐    ┌───────▼────────┐
   │   PostgreSQL    │    │  Redis + Celery │
   │   (Database)    │    │  (Task Queue)   │
   └─────────────────┘    └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │ Your Scripts    │
                          │ • dea_analysis  │
                          │ • vep_processing│
                          │ • join_results  │
                          │ • contingency   │
                          └─────────────────┘
```

## 📁 File Structure

```
bioworkflow/
├── app/                          # Main application package
│   ├── __init__.py              # Flask app factory
│   ├── models.py                # Database models (User, Project, Experiment, Result)
│   ├── auth/                    # Authentication blueprint
│   │   ├── forms.py            # Login/registration forms
│   │   └── routes.py           # Auth endpoints
│   ├── projects/                # Projects management
│   │   └── routes.py           # Project CRUD endpoints
│   ├── experiments/             # Experiments management
│   │   └── routes.py           # Experiment endpoints, file uploads
│   ├── services/                # Business logic
│   │   ├── pipeline.py         # ★ YOUR SCRIPTS INTEGRATION ★
│   │   └── tasks.py            # Celery async tasks
│   └── utils/                   # Helper utilities
│       ├── auth.py             # Auth decorators
│       └── files.py            # File handling utilities
│
├── scripts/                     # ★★★ YOUR SCRIPTS GO HERE ★★★
│   ├── README.md               # Detailed integration guide
│   ├── dea_analysis.py         # Script 1: Differential Expression Analysis
│   ├── vep_processing.py       # Script 2: VEP processing
│   ├── join_results.py         # Script 3: Join DEA + VEP
│   └── generate_contingency.py # Script 4: Generate contingency table
│
├── config.py                    # Configuration management
├── wsgi.py                      # WSGI entry point
├── requirements.txt             # Python dependencies
├── .env.example                # Environment variables template
├── gunicorn_config.py          # Gunicorn server config
├── nginx.conf.example          # Nginx reverse proxy config
│
├── systemd/                     # Systemd service files
│   ├── bioworkflow.service     # Gunicorn service
│   └── bioworkflow-celery.service  # Celery worker service
│
├── README.md                    # Main documentation
├── API.md                       # Complete API reference
├── DEPLOYMENT.md               # Step-by-step deployment guide
└── scripts/README.md           # Script integration guide
```

## 🔌 Integration Points for Your Scripts

### Where Your Scripts Are Called

**File:** `app/services/pipeline.py`

This is where your 4 bioinformatics scripts are integrated. The file contains:

1. **`run_script1_dea()`** - Calls your DEA analysis script
2. **`run_script2_vep()`** - Calls your VEP processing script
3. **`run_script3_join()`** - Calls your join script
4. **`run_script4_contingency()`** - Calls your contingency table script

Each function:
- Builds the command-line arguments for your script
- Executes the script using `subprocess`
- Captures stdout/stderr for logging
- Validates that output files were created
- Returns results to the pipeline orchestrator

### Script Requirements

Your scripts must:
1. Accept command-line arguments (shown in `scripts/README.md`)
2. Exit with code 0 on success, non-zero on failure
3. Write output to the exact path specified in `--output-file`
4. Be executable: `chmod +x scripts/*.py`

### Example Integration

```python
# In app/services/pipeline.py

def run_script1_dea(expression_dir, output_dir, experiment):
    """Execute your DEA script"""
    command = [
        'python3',  # Or path to conda env
        'scripts/dea_analysis.py',
        '--input-dir', str(expression_dir),
        '--output-file', str(output_dir / 'dea_results.csv'),
        '--experiment-id', str(experiment.id)
    ]
    
    result = subprocess.run(command, capture_output=True, check=True)
    # Script output is captured and logged
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
cd bioworkflow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Initialize Database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Add Your Scripts

Place your 4 bioinformatics scripts in the `scripts/` directory.

### 5. Test Development Server

```bash
# Terminal 1: Start Flask
flask run

# Terminal 2: Start Celery worker
celery -A app.celery worker --loglevel=info

# Terminal 3: Test API
curl http://localhost:5000/health
```

### 6. Production Deployment

See `DEPLOYMENT.md` for complete production setup with Nginx + Gunicorn.

## 📊 Data Flow

### User Workflow

1. **Register/Login** → User account created
2. **Create Project** → Container for related experiments
3. **Create Experiment** → Individual analysis run
4. **Upload Files** → Gene expression file + VCF files
5. **Run Pipeline** → Async execution of 4 scripts
6. **Monitor Progress** → Poll status endpoint
7. **Download Results** → Final contingency table

### Pipeline Execution

```
User triggers /experiments/<id>/run
    ↓
Celery task queued
    ↓
Status: queued → running
    ↓
Script 1: DEA Analysis
    Input: storage/uploads/{user}/{project}/{exp}/expression/
    Output: storage/intermediate/{user}/{project}/{exp}/dea_results.csv
    ↓
Script 2: VEP Processing
    Input: storage/uploads/{user}/{project}/{exp}/vcf/
    Output: storage/intermediate/{user}/{project}/{exp}/vep_results.csv
    ↓
Script 3: Join Results
    Input: dea_results.csv + vep_results.csv
    Output: storage/intermediate/{user}/{project}/{exp}/joined_results.csv
    ↓
Script 4: Generate Contingency Table
    Input: joined_results.csv
    Output: storage/results/{user}/{project}/{exp}/contingency_table.csv
    ↓
Result saved to database
    ↓
Status: completed
    ↓
User downloads via /experiments/<id>/download
```

## 🔒 Security Features

- **Password Hashing**: Bcrypt with salt
- **Session Management**: Secure HTTP-only cookies
- **CSRF Protection**: Flask-WTF tokens
- **File Validation**: Extension and size checks
- **Directory Isolation**: Per-user/project file separation
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries
- **Authentication Required**: Decorators on all sensitive endpoints
- **Access Control**: Users can only access their own projects/experiments

## 📈 Scalability Considerations

### Vertical Scaling
- Increase Gunicorn workers: `workers = multiprocessing.cpu_count() * 2 + 1`
- Increase Celery workers for more concurrent pipeline executions
- Add more Redis nodes for task queue distribution

### Horizontal Scaling
- Run multiple application servers behind load balancer
- Use shared PostgreSQL database
- Use shared Redis cluster
- Use shared file storage (NFS, S3, etc.)

### Performance Optimization
- Add caching layer (Redis, Memcached)
- Implement pagination for large result sets
- Add database indexes (already included in models)
- Use connection pooling (configured in SQLAlchemy)

## 🧪 Testing Your Scripts

Before full integration, test each script independently:

```bash
# Create test data
mkdir -p test_data/{expression,vcf} test_output

# Test Script 1
python scripts/dea_analysis.py \
    --input-dir test_data/expression \
    --output-file test_output/dea.csv \
    --experiment-id 1

# Test Script 2
python scripts/vep_processing.py \
    --vcf-dir test_data/vcf \
    --output-file test_output/vep.csv \
    --experiment-id 1

# Test Script 3
python scripts/join_results.py \
    --dea-file test_output/dea.csv \
    --vep-file test_output/vep.csv \
    --output-file test_output/joined.csv \
    --experiment-id 1

# Test Script 4
python scripts/generate_contingency.py \
    --input-file test_output/joined.csv \
    --output-file test_output/contingency.csv \
    --experiment-id 1
```

## 📚 Documentation

- **README.md** - Main overview and setup instructions
- **API.md** - Complete REST API documentation with examples
- **DEPLOYMENT.md** - Production deployment guide
- **scripts/README.md** - Detailed script integration guide

## 🔧 Customization Points

### Database
Currently configured for PostgreSQL (production) or SQLite (development).
To use MySQL, update `DATABASE_URL` in `.env` and install `mysqlclient`.

### File Storage
Currently uses local filesystem. To use S3:
1. Install `boto3`
2. Update `app/utils/files.py` to use S3 instead of local paths
3. Update configuration in `config.py`

### Additional Scripts
Need more than 4 scripts? Add them in `app/services/pipeline.py`:
1. Create `run_script5_xxx()` function
2. Add call in `execute_pipeline()`
3. Update progress tracking

### Authentication
Currently uses session-based auth. To use JWT:
1. Install `flask-jwt-extended`
2. Update `app/auth/routes.py`
3. Update authentication decorators

## ⚠️ Important Notes

### What This Provides
- ✅ Complete Flask backend infrastructure
- ✅ User authentication and session management
- ✅ Database models and migrations
- ✅ RESTful API endpoints
- ✅ File upload and storage handling
- ✅ Asynchronous pipeline execution
- ✅ Production deployment configuration
- ✅ Comprehensive documentation

### What You Need to Provide
- ❗ Your 4 bioinformatics analysis scripts
- ❗ Domain name for production (or use IP)
- ❗ SSL certificates (or use Let's Encrypt)
- ❗ Server/VM for deployment

### Scripts Are Placeholders
The scripts in `scripts/` directory create DUMMY OUTPUT for demonstration.
**You MUST replace them with your actual bioinformatics implementations.**

## 🎓 Next Steps

1. **Review the code** - Understand the architecture
2. **Read documentation** - Especially `scripts/README.md`
3. **Test locally** - Run development server
4. **Implement your scripts** - Replace placeholder scripts
5. **Test pipeline** - Upload real data and verify
6. **Deploy to production** - Follow `DEPLOYMENT.md`
7. **Monitor and optimize** - Check logs, tune performance

## 📞 Support

For deployment issues:
1. Check logs: `logs/bioworkflow.log` and `logs/celery_worker.log`
2. Review systemd status: `systemctl status bioworkflow`
3. Test components individually
4. Verify database connection
5. Check file permissions

## ✨ What Makes This Production-Ready

1. **Security**: Password hashing, CSRF protection, session security
2. **Scalability**: Async task queue, multi-worker design
3. **Reliability**: Error handling, logging, status tracking
4. **Maintainability**: Modular architecture, comprehensive docs
5. **Deployability**: Systemd services, Nginx config, migration system
6. **Monitoring**: Logging system, health check endpoint
7. **Extensibility**: Clean separation of concerns, plugin points

This is a **real, deployable application**, not a proof-of-concept. Every component has been designed with production use in mind.

---

**You now have a complete, production-ready backend infrastructure. Focus on implementing your bioinformatics analysis logic, and the platform will handle everything else!**
