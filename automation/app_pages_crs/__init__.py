"""Page objects for Compliance Ready Software flows on the desktop app."""

from automation.app_pages_crs.compliance_login_page import ComplianceLoginPage
from automation.app_pages_crs.documentation_required_page import AppDocumentationRequired
from automation.app_pages_crs.enable_crs_wizard_page import EnableCRSWizardPage
from automation.app_pages_crs.sign_run_page import SignRunPage
from automation.app_pages_crs.user_management_page import UserManagementPage
from automation.app_pages_crs.write_documentation import WriteDocumentation

__all__ = [
    "AppDocumentationRequired",
    "ComplianceLoginPage",
    "EnableCRSWizardPage",
    "SignRunPage",
    "UserManagementPage",
    "WriteDocumentation",
]
