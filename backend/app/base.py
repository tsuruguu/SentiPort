# app/base.py
# Ten plik importuje bazową klasę i wszystkie modele, żeby SQLAlchemy
# widziało całą strukturę bazy "w jednym miejscu".
from app.models.base import Base

# Importujemy wszystkie modele, by zarejestrowały się w Base.metadata
from app.models.company import Company
from app.models.vessel import Vessel
from app.models.reference import Port, Berth
from app.models.operations import Nomination
from app.models.risk import VesselRiskAssessment