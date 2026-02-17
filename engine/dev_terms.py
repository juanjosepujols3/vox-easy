"""
Built-in developer terminology for Whisper prompt boosting.
When dev mode is active, these terms are added to the Whisper prompt
to improve recognition of technical vocabulary.
"""

DEV_TERMS = [
    # Infrastructure
    "Kubernetes", "Docker", "Supabase", "Firebase", "AWS", "Vercel",
    "Netlify", "Terraform", "Nginx", "Apache", "Linux", "Ubuntu",
    # Frameworks
    "React", "Next.js", "Vue", "Angular", "FastAPI", "Django",
    "Express", "Node.js", "Spring Boot", "Laravel", "Flask", "Svelte",
    # Languages
    "TypeScript", "JavaScript", "Python", "Rust", "Go", "Swift",
    "Kotlin", "Java", "C++", "Ruby", "PHP", "Dart",
    # Databases
    "PostgreSQL", "MongoDB", "Redis", "SQLite", "MySQL", "DynamoDB",
    "Elasticsearch", "Cassandra",
    # Tools
    "VS Code", "Cursor", "Windsurf", "npm", "yarn", "pip", "cargo",
    "brew", "Git", "GitHub", "GitLab", "Bitbucket",
    # Concepts
    "API", "REST", "GraphQL", "WebSocket", "OAuth", "JWT",
    "CI/CD", "DevOps", "middleware", "webhook", "microservices",
    "serverless", "containerization", "Kubernetes",
    # Common terms Whisper often gets wrong
    "localhost", "endpoint", "frontend", "backend", "fullstack",
    "deployment", "repository", "pull request", "merge", "branch",
    "commit", "refactor", "debug", "async", "await", "callback",
    "promise", "observable", "useState", "useEffect",
]
