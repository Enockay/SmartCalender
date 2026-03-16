from __future__ import annotations

import platform
import subprocess
from datetime import datetime

from app.core.logger import get_logger


class SystemNotificationService:
    """Service for scheduling system-level notifications that work even when app is closed.
    
    On macOS, uses the `osascript` command to schedule notifications via AppleScript.
    This allows reminders to fire even when the application is closed.
    """
    
    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._is_macos = platform.system() == "Darwin"
        
    def schedule_notification(
        self,
        reminder_id: int,
        title: str,
        body: str,
        fire_date: datetime,
    ) -> bool:
        """Schedule a system notification that will fire even if app is closed.
        
        On macOS, creates an AppleScript that schedules a notification.
        Returns True if scheduled successfully, False otherwise.
        """
        if not self._is_macos:
            self._logger.warning("System notifications only supported on macOS")
            return False
        
        try:
            # Calculate delay in seconds
            now = datetime.now()
            delay_seconds = (fire_date - now).total_seconds()
            
            if delay_seconds <= 0:
                self._logger.warning(f"Reminder {reminder_id} is already past due")
                return False
            
            # Use osascript to schedule notification via AppleScript
            # This creates a background process that will fire even if app closes
            # Also plays sound 3 times
            escaped_body = body.replace('"', '\\"')
            escaped_title = title.replace('"', '\\"')
            
            # Create script that shows notification and plays sound 3 times
            # Use Glass.aiff as default system sound, or we could make it configurable
            script = f'''
            tell application "System Events"
                do shell script "sleep {int(delay_seconds)} && osascript -e 'display notification \\\"{escaped_body}\\\" with title \\\"{escaped_title}\\\" sound name \\\"Glass\\\"' && for i in {{1..3}}; do afplay /System/Library/Sounds/Glass.aiff; sleep 0.4; done"
            end tell
            '''
            
            # Run in background
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            self._logger.info(
                f"Scheduled system notification for reminder {reminder_id} "
                f"at {fire_date.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(will fire even if app is closed)"
            )
            return True
            
        except Exception as e:
            self._logger.error(f"Error scheduling system notification: {e}", exc_info=True)
            return False
    
    def check_missed_reminders(self, reminder_service) -> int:
        """Check for reminders that were due while app was closed.
        
        Returns count of missed reminders found.
        """
        now = datetime.now()
        # Get all reminders that are overdue but not dismissed
        missed = reminder_service.get_by_filter("overdue")
        
        count = 0
        for reminder in missed:
            # If reminder was due while app was closed, log it
            if reminder.remind_at < now:
                count += 1
                self._logger.info(
                    f"Found missed reminder: ID={reminder.id}, "
                    f"title='{reminder.title}', was due at {reminder.remind_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        
        if count > 0:
            self._logger.warning(
                f"⚠️  {count} reminder(s) were due while the app was closed. "
                f"Consider keeping the app running in the background for reliable reminders."
            )
        
        return count
