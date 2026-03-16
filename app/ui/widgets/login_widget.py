from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QFrame,
    QMessageBox,
    QApplication,
)

from app.services.auth_service import AuthService
from app.models.auth_response import AuthResponse
from app.database.db_manager import DatabaseManager
from app.database.schema import User
from sqlalchemy import select
from datetime import datetime


class LoginWorker(QThread):
    """Background worker for login API call."""
    
    finished = Signal(object)  # AuthResponse
    error = Signal(str)
    
    def __init__(self, auth_service: AuthService, email: str, password: str, remember_me: bool):
        super().__init__()
        self._auth_service = auth_service
        self._email = email
        self._password = password
        self._remember_me = remember_me
    
    def run(self):
        try:
            response = self._auth_service.login(self._email, self._password, self._remember_me)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class LoginWidget(QWidget):
    """Login splash screen widget."""
    
    loginSuccessful = Signal(AuthResponse)
    loginCancelled = Signal()
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LoginWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self._auth_service = AuthService()
        self._db = DatabaseManager()
        self._login_worker: LoginWorker | None = None
        
        self._build_ui()
        self._check_server_status()
        
        # Ensure QSS is applied after widget is built
        QTimer.singleShot(100, self._apply_styles)
        
        # Check if user is already logged in
        #QTimer.singleShot(100, self._check_existing_login)
    
    def _build_ui(self) -> None:
        """Build the login UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Background container - transparent to show window background
        container = QFrame(self)
        container.setObjectName("LoginContainer")
        container.setAttribute(Qt.WA_StyledBackground, True)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setAlignment(Qt.AlignCenter)
        
        # Login card
        card = QFrame(container)
        card.setObjectName("LoginCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        
        card_layout = QVBoxLayout(card)
        # Let the header bar touch the very top of the card and span full width.
        # Inner content below gets its own paddings.
        card_layout.setContentsMargins(0, 0, 0, 28)
        card_layout.setSpacing(0)
        
        # Header bar (separate area so we can style a different background + divider line)
        header_frame = QFrame(card)
        header_frame.setObjectName("LoginHeaderBar")
        header_frame.setAttribute(Qt.WA_StyledBackground, True)
        
        header_layout = QHBoxLayout(header_frame)
        # Increase bottom padding to make the header band visually taller
        header_layout.setContentsMargins(40, 20, 40, 32)
        header_layout.setSpacing(12)
        header_layout.setAlignment(Qt.AlignCenter)
        
        icon_label = QLabel("📅", header_frame)
        icon_label.setObjectName("LoginIcon")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel("Smart Calender", header_frame)
        title_label.setObjectName("LoginTitle")
        header_layout.addWidget(title_label)
        
        card_layout.addWidget(header_frame)
        
        # Inner content area with side padding
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(40, 12, 40, 0)
        content_layout.setSpacing(18)
        card_layout.addLayout(content_layout)
        
        # Login heading
        heading_label = QLabel("Log In", card)
        heading_label.setObjectName("LoginHeading")
        heading_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(heading_label)
        
        # Email field
        email_layout = QVBoxLayout()
        email_layout.setContentsMargins(0, 0, 0, 0)
        email_layout.setSpacing(8)
        
        email_label = QLabel("Email Address", card)
        email_label.setObjectName("LoginFieldLabel")
        email_layout.addWidget(email_label)
        
        self._email_input = QLineEdit(card)
        self._email_input.setObjectName("LoginEmailInput")
        self._email_input.setPlaceholderText("Email Address")
        self._email_input.setMaxLength(255)
        email_layout.addWidget(self._email_input)
        
        content_layout.addLayout(email_layout)
        
        # Password field
        password_layout = QVBoxLayout()
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(8)
        
        password_label = QLabel("Password", card)
        password_label.setObjectName("LoginFieldLabel")
        password_layout.addWidget(password_label)
        
        self._password_input = QLineEdit(card)
        self._password_input.setObjectName("LoginPasswordInput")
        self._password_input.setPlaceholderText("Password")
        self._password_input.setEchoMode(QLineEdit.Password)
        self._password_input.setMaxLength(255)
        password_layout.addWidget(self._password_input)
        
        content_layout.addLayout(password_layout)
        
        # Options row
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(0)
        
        self._remember_checkbox = QCheckBox("Remember Me", card)
        self._remember_checkbox.setObjectName("LoginRememberCheckbox")
        options_layout.addWidget(self._remember_checkbox)
        
        options_layout.addStretch()
        
        forgot_link = QLabel("Forgot Password?", card)
        forgot_link.setObjectName("LoginForgotLink")
        forgot_link.setCursor(Qt.PointingHandCursor)
        options_layout.addWidget(forgot_link)
        
        content_layout.addLayout(options_layout)
        
        # Buttons row
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(12)
        
        self._login_button = QPushButton("Log In", card)
        self._login_button.setObjectName("LoginButton")
        self._login_button.setCursor(Qt.PointingHandCursor)
        self._login_button.clicked.connect(self._on_login_clicked)
        buttons_layout.addWidget(self._login_button)
        
        self._create_account_button = QPushButton("Create Account", card)
        self._create_account_button.setObjectName("CreateAccountButton")
        self._create_account_button.setCursor(Qt.PointingHandCursor)
        self._create_account_button.clicked.connect(self._on_create_account_clicked)
        buttons_layout.addWidget(self._create_account_button)
        
        content_layout.addLayout(buttons_layout)
        
        # Server status
        self._status_label = QLabel("Server status: Checking...", card)
        self._status_label.setObjectName("LoginStatusLabel")
        self._status_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self._status_label)
        
        container_layout.addWidget(card, alignment=Qt.AlignCenter)
        
        main_layout.addWidget(container)
    
    def _apply_styles(self) -> None:
        """Apply styles to ensure they're loaded."""
        # Force style reapplication for all widgets
        app = QApplication.instance()
        if app:
            # Unpolish and polish all widgets to refresh styles
            for widget in self.findChildren(QWidget):
                app.style().unpolish(widget)
                app.style().polish(widget)
                widget.update()
            
            # Also update self
            app.style().unpolish(self)
            app.style().polish(self)
            self.update()
    
    def _check_server_status(self) -> None:
        """Check and update server status."""
        def update_status():
            is_connected = self._auth_service.check_server_status()
            if is_connected:
                self._status_label.setText("Server status: Connected")
                self._status_label.setProperty("status", "connected")
            else:
                self._status_label.setText("Server status: Disconnected")
                self._status_label.setProperty("status", "disconnected")
            self._status_label.style().unpolish(self._status_label)
            self._status_label.style().polish(self._status_label)
        
        # Run in background
        QTimer.singleShot(500, update_status)
    
    def _check_existing_login(self) -> None:
        """Check if user is already logged in."""
        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User).where(User.is_logged_in == True).limit(1)
                ).scalar_one_or_none()
                
                if user and user.is_logged_in:
                    # Auto-login if token is still valid
                    if user.token_expires_at and user.token_expires_at > datetime.utcnow():
                        # Create AuthResponse from stored data
                        auth_response = AuthResponse(
                            user_id=user.api_user_id or str(user.id),
                            email=user.email,
                            name=user.name or "",
                            access_token=user.access_token or "",
                            refresh_token=user.refresh_token,
                            token_expires_at=user.token_expires_at,
                            subscription_tier=user.subscription_tier or "free",
                            subscription_status=user.subscription_status or "active",
                            subscription_expires_at=user.subscription_expires_at,
                            subscription_features=json.loads(user.subscription_features) if user.subscription_features else [],
                            timezone=user.timezone,
                            language=user.language,
                            avatar_url=user.avatar_url,
                            organization_id=user.organization_id,
                            organization_name=user.organization_name,
                            role=user.role,
                        )
                        self.loginSuccessful.emit(auth_response)
                        return
        except Exception:
            pass  # If check fails, show login screen
    
    def _on_login_clicked(self) -> None:
        """Handle login button click."""
        email = self._email_input.text().strip()
        password = self._password_input.text()
        remember_me = self._remember_checkbox.isChecked()
        
        # Validation
        if not email:
            QMessageBox.warning(self, "Validation Error", "Please enter your email address.")
            self._email_input.setFocus()
            return
        
        if not password:
            QMessageBox.warning(self, "Validation Error", "Please enter your password.")
            self._password_input.setFocus()
            return
        
        # Disable inputs during login
        self._set_inputs_enabled(False)
        self._login_button.setText("Logging in...")
        
        # Start login worker
        self._login_worker = LoginWorker(self._auth_service, email, password, remember_me)
        self._login_worker.finished.connect(self._on_login_success)
        self._login_worker.error.connect(self._on_login_error)
        self._login_worker.start()
    
    def _on_create_account_clicked(self) -> None:
        """Handle create account button click."""
        QMessageBox.information(
            self,
            "Create Account",
            "Please visit our website to create an account.\n\n"
            "You can sign up at: https://smartcalender.com/signup"
        )
    
    def _on_login_success(self, auth_response: AuthResponse) -> None:
        """Handle successful login."""
        try:
            # Save user data to database
            self._save_user_data(auth_response)
            
            # Emit success signal
            self.loginSuccessful.emit(auth_response)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save user data: {str(e)}"
            )
            self._set_inputs_enabled(True)
            self._login_button.setText("Log In")
    
    def _on_login_error(self, error_message: str) -> None:
        """Handle login error."""
        QMessageBox.warning(self, "Login Failed", error_message)
        self._set_inputs_enabled(True)
        self._login_button.setText("Log In")
    
    def _set_inputs_enabled(self, enabled: bool) -> None:
        """Enable or disable input fields."""
        self._email_input.setEnabled(enabled)
        self._password_input.setEnabled(enabled)
        self._remember_checkbox.setEnabled(enabled)
        self._login_button.setEnabled(enabled)
        self._create_account_button.setEnabled(enabled)
    
    def _save_user_data(self, auth_response: AuthResponse) -> None:
        """Save authentication data to database."""
        with self._db.session() as session:
            # First, mark all users as logged out so only one "current" user exists.
            session.query(User).update({User.is_logged_in: False})
            
            # Check if user exists
            user = session.execute(
                select(User).where(User.email == auth_response.email).limit(1)
            ).scalar_one_or_none()
            
            if not user:
                # Create new user
                user = User(
                    email=auth_response.email,
                    name=auth_response.name,
                    subscription_tier=auth_response.subscription_tier,
                    subscription_status=auth_response.subscription_status,
                    subscription_expires_at=auth_response.subscription_expires_at,
                    subscription_features=json.dumps(auth_response.subscription_features) if auth_response.subscription_features else None,
                    access_token=auth_response.access_token,
                    refresh_token=auth_response.refresh_token,
                    token_expires_at=auth_response.token_expires_at,
                    api_user_id=auth_response.user_id,
                    timezone=auth_response.timezone,
                    language=auth_response.language,
                    avatar_url=auth_response.avatar_url,
                    organization_id=auth_response.organization_id,
                    organization_name=auth_response.organization_name,
                    role=auth_response.role,
                    is_logged_in=True,
                    last_login_at=datetime.utcnow(),
                )
                session.add(user)
            else:
                # Update existing user
                user.name = auth_response.name
                user.subscription_tier = auth_response.subscription_tier
                user.subscription_status = auth_response.subscription_status
                user.subscription_expires_at = auth_response.subscription_expires_at
                user.subscription_features = json.dumps(auth_response.subscription_features) if auth_response.subscription_features else None
                user.access_token = auth_response.access_token
                user.refresh_token = auth_response.refresh_token
                user.token_expires_at = auth_response.token_expires_at
                user.api_user_id = auth_response.user_id
                user.timezone = auth_response.timezone
                user.language = auth_response.language
                user.avatar_url = auth_response.avatar_url
                user.organization_id = auth_response.organization_id
                user.organization_name = auth_response.organization_name
                user.role = auth_response.role
                user.is_logged_in = True
                user.last_login_at = datetime.utcnow()
            
            session.commit()
    
    def showEvent(self, event: QShowEvent) -> None:
        """Override showEvent to focus email input."""
        super().showEvent(event)
        # Focus email input
        QTimer.singleShot(100, self._email_input.setFocus)
