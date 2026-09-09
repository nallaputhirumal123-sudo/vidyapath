"""The jobs somebody can practise for, by name.

The trainer used to offer six role families — "Networking", "Software
engineering", "Sales" — and nobody interviews for a family. They interview
for Network Engineer, or BIM Coordinator, or Site Reliability Engineer, and
the questions for those three have almost nothing in common. A family is a
shelf; this is what is on it.

Two sources, merged:

  * this catalogue, written out per family. It is deliberately broader than
    the job board: the board is whatever was crawled this week, and a person
    preparing for a BIM/CAD interview should not be told that role does not
    exist because nobody advertised one on Tuesday.

  * the live board's own titles, added by the endpoint that serves this.
    Those are the roles actually being hired for, with a count, and they
    keep the list honest about the market as it is today.

Nothing here is generated. It is a list, it costs nothing to serve, and it
cannot invent a job that does not exist — which a model asked for "roles in
construction" certainly would.

Kept out of main.py the way craxlearn.py is: this is domain data, not
plumbing, and four hundred job titles in the middle of the application file
would bury the code around them.
"""

# Role titles per category id. The ids are CATEGORY_LABELS' own, so anything
# added here shows up wherever categories already do.
#
# Ordered roughly by how common the role is, because the list is read top
# down and the first screen should hold the ones most people want.
ROLES = {
    "network": [
        "Network Engineer", "Network Administrator", "Network Architect",
        "NOC Engineer", "Network Security Engineer", "Wireless Network Engineer",
        "Network Automation Engineer", "Telecom Engineer", "VoIP Engineer",
        "Data Centre Network Engineer", "Field Network Engineer",
        "Network Support Engineer", "Routing and Switching Engineer",
        "SD-WAN Engineer", "Network Operations Manager",
    ],
    "security": [
        "Security Analyst", "SOC Analyst", "Penetration Tester",
        "Information Security Engineer", "Security Engineer",
        "Cloud Security Engineer", "Application Security Engineer",
        "Incident Response Analyst", "Threat Intelligence Analyst",
        "GRC Analyst", "Identity and Access Management Engineer",
        "Vulnerability Management Analyst", "Security Architect",
        "Forensics Analyst", "Chief Information Security Officer",
    ],
    "sysadmin": [
        "System Administrator", "IT Support Engineer", "Desktop Support Engineer",
        "Linux Administrator", "Windows Administrator", "IT Helpdesk Analyst",
        "Server Administrator", "Active Directory Administrator",
        "Virtualisation Engineer", "Backup Administrator", "IT Asset Manager",
        "Service Desk Team Lead", "Endpoint Engineer", "IT Operations Manager",
    ],
    "devops": [
        "DevOps Engineer", "Site Reliability Engineer", "Platform Engineer",
        "Cloud Engineer", "AWS Engineer", "Azure Engineer",
        "Kubernetes Engineer", "Infrastructure Engineer",
        "Build and Release Engineer", "CI/CD Engineer",
        "Cloud Architect", "Observability Engineer", "DevSecOps Engineer",
        "Systems Engineer", "Automation Engineer",
    ],
    "backend": [
        "Backend Engineer", "Software Engineer", "Full Stack Developer",
        "Java Developer", "Python Developer", "Node.js Developer",
        ".NET Developer", "Golang Developer", "PHP Developer",
        "Ruby on Rails Developer", "API Developer", "Microservices Engineer",
        "Software Development Engineer", "Technical Lead",
        "Engineering Manager", "Solutions Architect", "C++ Developer",
        "Embedded Software Engineer", "Blockchain Developer",
    ],
    "frontend": [
        "Frontend Engineer", "React Developer", "Angular Developer",
        "Vue Developer", "UI Developer", "Web Developer",
        "JavaScript Developer", "TypeScript Developer",
        "WordPress Developer", "Shopify Developer", "Web Accessibility Engineer",
        "Frontend Architect",
    ],
    "mobile": [
        "Android Developer", "iOS Developer", "React Native Developer",
        "Flutter Developer", "Mobile Application Developer",
        "Kotlin Developer", "Swift Developer", "Mobile QA Engineer",
        "Mobile Architect",
    ],
    "data": [
        "Data Analyst", "Data Engineer", "Business Intelligence Analyst",
        "Analytics Engineer", "Database Administrator", "SQL Developer",
        "Data Warehouse Engineer", "ETL Developer", "Big Data Engineer",
        "Power BI Developer", "Tableau Developer", "Reporting Analyst",
        "Data Architect", "Snowflake Engineer", "Data Quality Analyst",
    ],
    "ml": [
        "Machine Learning Engineer", "Data Scientist", "AI Engineer",
        "MLOps Engineer", "Computer Vision Engineer", "NLP Engineer",
        "Deep Learning Engineer", "Research Scientist",
        "LLM Engineer", "Prompt Engineer", "Applied Scientist",
        "AI Product Engineer", "Generative AI Engineer",
    ],
    "qa": [
        "QA Engineer", "Test Engineer", "Automation Test Engineer",
        "SDET", "Manual Tester", "Performance Test Engineer",
        "Selenium Automation Engineer", "QA Lead", "Test Analyst",
        "Quality Assurance Manager", "API Test Engineer",
    ],
    "product": [
        "Product Manager", "Associate Product Manager", "Product Owner",
        "Technical Program Manager", "Project Manager", "Scrum Master",
        "Programme Manager", "Business Analyst", "Product Analyst",
        "Delivery Manager", "Agile Coach", "Group Product Manager",
    ],
    "design": [
        "UI/UX Designer", "Product Designer", "UX Researcher",
        "Graphic Designer", "Visual Designer", "Interaction Designer",
        "Motion Designer", "Design Systems Designer", "Web Designer",
        "Brand Designer", "Illustrator", "Design Lead",
    ],
    "sales": [
        "Sales Executive", "Business Development Executive",
        "Account Executive", "Inside Sales Representative",
        "Sales Development Representative", "Key Account Manager",
        "Territory Sales Manager", "Regional Sales Manager",
        "Solution Consultant", "Pre-Sales Engineer", "Sales Manager",
        "Channel Partner Manager", "Enterprise Sales Manager",
        "Field Sales Executive", "Telesales Executive",
    ],
    "marketing": [
        "Digital Marketing Executive", "Marketing Manager",
        "SEO Specialist", "Content Marketing Manager",
        "Social Media Manager", "Performance Marketing Manager",
        "Growth Marketer", "Brand Manager", "Email Marketing Specialist",
        "Marketing Analyst", "Product Marketing Manager",
        "PPC Specialist", "Influencer Marketing Manager",
    ],
    "support": [
        "Customer Support Executive", "Customer Success Manager",
        "Technical Support Engineer", "Customer Service Representative",
        "Support Team Lead", "Client Relationship Manager",
        "Onboarding Specialist", "Account Manager",
        "Call Centre Executive", "Chat Support Executive",
    ],
    "finance": [
        "Accountant", "Financial Analyst", "Accounts Payable Executive",
        "Accounts Receivable Executive", "Chartered Accountant",
        "Auditor", "Internal Auditor", "Tax Consultant",
        "Finance Manager", "Cost Accountant", "Treasury Analyst",
        "Investment Analyst", "Credit Analyst", "Payroll Executive",
        "GST Executive", "Bookkeeper",
    ],
    "hr": [
        "HR Executive", "Recruiter", "Technical Recruiter",
        "HR Business Partner", "Talent Acquisition Specialist",
        "HR Manager", "Payroll and Compliance Executive",
        "Learning and Development Executive", "HR Generalist",
        "Employee Relations Specialist", "Compensation and Benefits Analyst",
        "Campus Recruiter",
    ],
    "legal": [
        "Legal Counsel", "Corporate Lawyer", "Compliance Officer",
        "Contract Manager", "Paralegal", "Legal Associate",
        "Company Secretary", "Intellectual Property Analyst",
        "Data Protection Officer", "Litigation Associate",
    ],
    "operations": [
        "Operations Executive", "Supply Chain Analyst",
        "Logistics Coordinator", "Warehouse Manager",
        "Procurement Executive", "Inventory Analyst",
        "Operations Manager", "Planning Manager", "Store Manager",
        "Vendor Manager", "Import Export Executive",
        "Demand Planner", "Distribution Manager",
    ],
    "admin": [
        "Office Administrator", "Executive Assistant",
        "Administrative Assistant", "Front Office Executive",
        "Data Entry Operator", "Receptionist", "Facilities Coordinator",
        "Office Manager", "Personal Assistant",
    ],
    "consulting": [
        "Business Analyst", "Management Consultant",
        "Functional Consultant", "SAP Consultant", "Salesforce Consultant",
        "ERP Consultant", "Process Analyst", "Strategy Analyst",
        "Technology Consultant", "Implementation Consultant",
    ],
    "healthcare": [
        "Staff Nurse", "Medical Officer", "Pharmacist",
        "Lab Technician", "Radiographer", "Physiotherapist",
        "Clinical Research Associate", "Medical Coder",
        "Hospital Administrator", "Dietitian", "Dental Assistant",
        "Healthcare Data Analyst", "Medical Representative",
    ],
    "education": [
        "Teacher", "Lecturer", "Assistant Professor",
        "Academic Coordinator", "Subject Matter Expert",
        "Corporate Trainer", "Instructional Designer",
        "Curriculum Developer", "Special Education Teacher",
        "Education Counsellor", "Teaching Assistant", "Principal",
    ],
    # The family the trainer was originally asked for and did not have.
    "manufacturing": [
        "Mechanical Engineer", "Design Engineer", "CAD Engineer",
        "BIM Coordinator", "BIM Modeller", "Revit Modeller",
        "MEP Design Engineer", "Electrical Design Engineer",
        "Production Engineer", "Quality Engineer", "Maintenance Engineer",
        "Manufacturing Engineer", "Process Engineer", "Industrial Engineer",
        "Tool and Die Engineer", "CNC Programmer", "Piping Design Engineer",
        "HVAC Design Engineer", "Product Design Engineer",
        "Plant Engineer", "Instrumentation Engineer", "Draughtsman",
    ],
    "construction": [
        "Civil Engineer", "Site Engineer", "Structural Engineer",
        "Quantity Surveyor", "Project Engineer", "Construction Manager",
        "Site Supervisor", "Planning Engineer", "Billing Engineer",
        "Architect", "Interior Designer", "Surveyor",
        "Safety Officer", "Estimation Engineer", "Contracts Engineer",
        "Highway Engineer", "Geotechnical Engineer",
    ],
    "hospitality": [
        "Chef", "Commis Chef", "Restaurant Manager",
        "Front Office Executive", "Housekeeping Supervisor",
        "Food and Beverage Executive", "Hotel Manager", "Bartender",
        "Banquet Manager", "Guest Relations Executive", "Travel Consultant",
    ],
    "retail": [
        "Store Manager", "Retail Sales Associate", "Cashier",
        "Visual Merchandiser", "Category Manager", "Area Sales Manager",
        "Retail Operations Manager", "Stock Assistant",
        "E-commerce Executive",
    ],
    "driver": [
        "Delivery Executive", "Driver", "Heavy Vehicle Driver",
        "Fleet Supervisor", "Logistics Executive", "Rider",
        "Dispatch Coordinator",
    ],
    "science": [
        "Research Associate", "Lab Chemist", "Quality Control Analyst",
        "Microbiologist", "Biotechnologist", "Formulation Scientist",
        "Analytical Chemist", "Research Scientist",
        "Regulatory Affairs Executive", "Clinical Data Manager",
    ],
    "writing": [
        "Content Writer", "Technical Writer", "Copywriter",
        "Editor", "Content Strategist", "Documentation Specialist",
        "Proofreader", "Scriptwriter", "UX Writer", "Journalist",
    ],
    "other": [
        "Technical Specialist", "Operations Analyst", "Programme Coordinator",
        "Field Engineer", "Application Engineer", "Service Engineer",
    ],
}


def all_roles():
    """Every role, once, with the family it belongs to."""
    out = []
    for cat, names in ROLES.items():
        for n in names:
            out.append({"role": n, "category": cat})
    return out


def _norm(s):
    return " ".join(str(s or "").lower().split())


def search(q, category="", limit=40):
    """Roles matching what somebody typed.

    A prefix match ranks above a match in the middle, because somebody typing
    "data" wants Data Analyst before Clinical Data Manager. Below that,
    shorter titles first: the plainer the name, the more likely it is the one
    meant.
    """
    q = _norm(q)
    cat = (category or "").strip().lower()
    hits = []
    for cat_id, names in ROLES.items():
        if cat and cat_id != cat:
            continue
        for n in names:
            ln = _norm(n)
            if not q:
                hits.append((2, len(n), n, cat_id))
            elif ln.startswith(q):
                hits.append((0, len(n), n, cat_id))
            elif q in ln:
                hits.append((1, len(n), n, cat_id))
    hits.sort()
    return [{"role": n, "category": c} for _r, _l, n, c in hits[:max(1, limit)]]
