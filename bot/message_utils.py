# fx/bot/message_utils.py
import logging
import telegram
from telegram import Update
from typing import Optional, Any

logger = logging.getLogger(__name__)

async def safe_edit_message(
    query: telegram.CallbackQuery,
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Any] = None,
    **kwargs
) -> bool:
    """
    Safely edit a message, ignoring "Message not modified" errors.
    Returns True if message was edited, False if it was already current.
    """
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs
        )
        return True
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            # Message is already showing the same content - this is fine
            logger.debug("Message already current, ignoring edit error")
            return False
        else:
            # Re-raise other BadRequest errors
            logger.error(f"BadRequest error editing message: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error editing message: {e}")
        raise