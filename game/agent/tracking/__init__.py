"""Optional local experiment tracking; importing this package requires no MLflow."""

from .reporting import TrackingConfig, report_progress, tracking_session

__all__ = ['TrackingConfig', 'report_progress', 'tracking_session']
