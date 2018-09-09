"""
Stores and manages the connections of users and other IRC servers
"""
import logging
from typing import Optional, TypeVar, Type, TYPE_CHECKING

from include.connection import Connection

from models import Error, User, Server, BaseModel

LOG = logging.getLogger(__name__)


TActor = TypeVar("TActor", bound="Actor")


class Actor(BaseModel[Connection, TActor]):
    """The connection and related methods of a single user or server"""

    connection: Connection

    def __init__(self, connection: Connection, **kwargs) -> None:
        super().__init__(connection)
        self.password = None

        self._server: Optional[Server] = None
        self._user: Optional[User] = None
        if "user" in kwargs:
            self.user = kwargs["user"]
        if "server" in kwargs:
            self.server = kwargs["server"]

    @property
    def disconnected(self) -> bool:
        """Whether this server has marked the connection as done"""
        return self.connection.disconnected

    @property
    def connection_dropped(self) -> bool:
        """Whether the connection has been unexpectedly lost"""
        return self.connection.connection_dropped

    # Model stuff

    def get_key(self) -> Connection:
        return self.connection

    def _set_key(self, new_key: Connection):
        self.connection = new_key

    # Union of User and Server
    def is_user(self) -> bool:
        """Is this `Actor` managing the connection of a user?"""
        return self._user is not None

    def is_server(self) -> bool:
        """Is this `Actor` managing the connection of a server?"""
        return self._server is not None

    def get_user(self) -> User:
        """Get the `User` this `Actor` is managing the connection for"""
        if self._user is not None:
            return self._user
        raise Error("not a user")

    def get_server(self) -> Server:
        """Get the `Server` this `Actor` is managing the connection for"""
        if self._server is not None:
            return self._server
        raise Error("not a server")

    def __setattr__(self, key, value):
        if key == "server":
            if self.is_user():
                raise Error("user XOR server must be passed to Actor")
            if value.actor:
                raise Error("server already has an actor set")
            self._server = value
            self._server.actor = self
        elif key == "user":
            if self.is_server():
                raise Error("user XOR server must be passed to Actor")
            if value.actor:
                raise Error("user already has an actor set")
            self._user = value
            self._user.actor = self
        else:
            super(Actor, self).__setattr__(key, value)

    def __str__(self):
        if self.is_user():
            return "Actor(" + str(self.get_user()) + ")"
        if self.is_server():
            return "Actor(" + str(self.get_server()) + ")"
        return "Unknown Actor"

    def __repr__(self):
        return str(self)

    # Implement socket-like interface
    def write(self, message: "Message") -> None:
        """Serialize and write a `Message` onto the connection managed by this `Actor`"""
        if self.is_user() and message.add_nick:
            message.parameters.insert(0, self.get_user().nickname)
        # pylint: disable=bare-except
        try:
            self.connection.write(message)
        except:
            self.connection.connection_dropped = True
            LOG.exception("Connection dropped for %s, write() call failed", self)
        # pylint: enable=bare-except

        if self.is_user() and message.add_nick:
            message.parameters = message.parameters[1:]

    async def flush(self):
        """Flush the write buffer of the managed connection"""
        # pylint: disable=bare-except
        try:
            return await self.connection.drain()
        except:
            self.connection.connection_dropped = True
            LOG.exception("Connection dropped for %s, flush() call failed", self)
        # pylint: enable=bare-except

    def disconnect(self):
        """Mark this connection as over"""
        self.connection.disconnect()

    def __iter__(self):
        return iter([self])


# pylint: disable=wrong-import-position,unused-import
# Import Message at the end to break circular dependency between Actor and Message.
# We need it only for type-checking, and `if typing.TYPE_CHECKING` didn't seem to work.
from include.message import Message
