"""Page objects for Compliance Ready Software flows on the desktop app."""

from automation.app_pages_crs.compliance_login_page import ComplianceLoginPage
from automation.app_pages_crs.documentation_required_page import AppDocumentationRequired
from automation.app_pages_crs.enable_crs_wizard_page import EnableCRSWizardPage

__all__ = [
    "AppDocumentationRequired",
    "ComplianceLoginPage",
    "EnableCRSWizardPage",
]
