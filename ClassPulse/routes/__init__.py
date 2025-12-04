# Import all route blueprints
from .pages import pages_bp
from .polling_api import polling_bp
from .questions_api import questions_bp
from .voting_api import voting_bp

# Create a list of blueprints to register in the app
blueprints = [pages_bp, polling_bp, questions_bp, voting_bp]