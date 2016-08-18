# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Mail protocol support.
"""

from __future__ import absolute_import, division

from twisted.mail import pop3
from twisted.mail import smtp
from twisted.internet import protocol
from twisted.internet import defer
from twisted.copyright import longversion
from twisted.python import log
from twisted.python.compat import networkString

from twisted.cred.credentials import CramMD5Credentials, UsernamePassword
from twisted.cred.error import UnauthorizedLogin

from twisted.mail import relay

from zope.interface import implementer



@implementer(smtp.IMessageDelivery)
class DomainDeliveryBase:
    """
    A base class for message delivery using the domains of a mail service.

    @ivar service: See L{__init__}
    @ivar user: See L{__init__}
    @ivar host: See L{__init__}

    @type protocolName: L{bytes}
    @ivar protocolName: The protocol being used to deliver the mail.
        Sub-classes should set this appropriately.
    """
    service = None
    protocolName = None

    def __init__(self, service, user, host=smtp.DNSNAME):
        """
        @type service: L{MailService}
        @param service: A mail service.

        @type user: L{bytes} or L{None}
        @param user: The authenticated SMTP user.

        @type host: L{bytes}
        @param host: The hostname.
        """
        self.service = service
        self.user = user
        self.host = host


    def receivedHeader(self, helo, origin, recipients):
        """
        Generate a received header string for a message.

        @type helo: 2-L{tuple} of (L{bytes}, L{bytes})
        @param helo: The client's identity as sent in the HELO command and its
            IP address.

        @type origin: L{Address}
        @param origin: The origination address of the message.

        @type recipients: L{list} of L{User}
        @param recipients: The destination addresses for the message.

        @rtype: L{bytes}
        @return: A received header string.
        """
        authStr = heloStr = b""
        if self.user:
            authStr = b" auth=" + self.user.encode('xtext')
        if helo[0]:
            heloStr = b" helo=" + helo[0]
        from_ = (b"from " + helo[0] + b" ([" + helo[1] + b"]" +
                 heloStr + authStr)
        by = (b"by " + self.host + b" with " + self.protocolName +
              b" (" + networkString(longversion) + b")")
        for_ = (b"for <" + b' '.join(map(bytes, recipients)) + b"> " +
                smtp.rfc822date())
        print(from_)
        print(by)
        print(for_)
        return b"Received: " + from_ + b"\n\t" + by + b"\n\t" + for_


    def validateTo(self, user):
        """
        Validate the address for which a message is destined.

        @type user: L{User}
        @param user: The destination address.

        @rtype: L{Deferred <defer.Deferred>} which successfully fires with
            no-argument callable which returns L{IMessage <smtp.IMessage>}
            provider.
        @return: A deferred which successfully fires with a no-argument
            callable which returns a message receiver for the destination.

        @raise SMTPBadRcpt: When messages cannot be accepted for the
            destination address.
        """
        # XXX - Yick.  This needs cleaning up.
        if self.user and self.service.queue:
            d = self.service.domains.get(user.dest.domain, None)
            if d is None:
                d = relay.DomainQueuer(self.service, True)
        else:
            d = self.service.domains[user.dest.domain]
        return defer.maybeDeferred(d.exists, user)


    def validateFrom(self, helo, origin):
        """
        Validate the address from which a message originates.

        @type helo: 2-L{tuple} of (L{bytes}, L{bytes})
        @param helo: The client's identity as sent in the HELO command and its
            IP address.

        @type origin: L{Address}
        @param origin: The origination address of the message.

        @rtype: L{Address}
        @return: The origination address.

        @raise SMTPBadSender: When messages cannot be accepted from the
            origination address.
        """
        if not helo:
            raise smtp.SMTPBadSender(origin, 503, "Who are you?  Say HELO first.")
        if origin.local != b'' and origin.domain == b'':
            raise smtp.SMTPBadSender(origin, 501, "Sender address must contain domain.")
        return origin



class SMTPDomainDelivery(DomainDeliveryBase):
    """
    A domain delivery base class for use in an SMTP server.
    """
    protocolName = b'smtp'



class ESMTPDomainDelivery(DomainDeliveryBase):
    """
    A domain delivery base class for use in an ESMTP server.
    """
    protocolName = b'esmtp'



class DomainSMTP(SMTPDomainDelivery, smtp.SMTP):
    """
    An SMTP server which uses the domains of a mail service.
    """
    service = user = None

    def __init__(self, *args, **kw):
        """
        Initialize the SMTP server.

        @type args: 2-L{tuple} of (L{IMessageDelivery} provider or
            L{None}, L{IMessageDeliveryFactory}
            provider or L{None})
        @param args: Positional arguments for L{SMTP.__init__}

        @type kw: L{dict}
        @param kw: Keyword arguments for L{SMTP.__init__}.
        """
        import warnings
        warnings.warn(
            "DomainSMTP is deprecated.  Use IMessageDelivery objects instead.",
            DeprecationWarning, stacklevel=2,
        )
        smtp.SMTP.__init__(self, *args, **kw)
        if self.delivery is None:
            self.delivery = self



class DomainESMTP(ESMTPDomainDelivery, smtp.ESMTP):
    """
    An ESMTP server which uses the domains of a mail service.
    """
    service = user = None

    def __init__(self, *args, **kw):
        """
        Initialize the ESMTP server.

        @type args: 2-L{tuple} of (L{IMessageDelivery} provider or
            L{None}, L{IMessageDeliveryFactory}
            provider or L{None})
        @param args: Positional arguments for L{ESMTP.__init__}

        @type kw: L{dict}
        @param kw: Keyword arguments for L{ESMTP.__init__}.
        """
        import warnings
        warnings.warn(
            "DomainESMTP is deprecated.  Use IMessageDelivery objects instead.",
            DeprecationWarning, stacklevel=2,
        )
        smtp.ESMTP.__init__(self, *args, **kw)
        if self.delivery is None:
            self.delivery = self



class SMTPFactory(smtp.SMTPFactory):
    """
    An SMTP server protocol factory.

    @ivar service: See L{__init__}
    @ivar portal: See L{__init__}

    @type protocol: no-argument callable which returns a L{Protocol
        <protocol.Protocol>} subclass
    @ivar protocol: A callable which creates a protocol.  The default value is
        L{SMTP}.
    """
    protocol = smtp.SMTP
    portal = None

    def __init__(self, service, portal = None):
        """
        @type service: L{MailService}
        @param service: An email service.

        @type portal: L{Portal <twisted.cred.portal.Portal>} or
            L{None}
        @param portal: A portal to use for authentication.
        """
        smtp.SMTPFactory.__init__(self)
        self.service = service
        self.portal = portal


    def buildProtocol(self, addr):
        """
        Create an instance of an SMTP server protocol.

        @type addr: L{IAddress <twisted.internet.interfaces.IAddress>} provider
        @param addr: The address of the SMTP client.

        @rtype: L{SMTP}
        @return: An SMTP protocol.
        """
        log.msg('Connection from %s' % (addr,))
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.service = self.service
        p.portal = self.portal
        return p



class ESMTPFactory(SMTPFactory):
    """
    An ESMTP server protocol factory.

    @type protocol: no-argument callable which returns a L{Protocol
        <protocol.Protocol>} subclass
    @ivar protocol: A callable which creates a protocol.  The default value is
        L{ESMTP}.

    @type context: L{IOpenSSLContextFactory
        <twisted.internet.interfaces.IOpenSSLContextFactory>} or L{None}
    @ivar context: A factory to generate contexts to be used in negotiating
        encrypted communication.

    @type challengers: L{dict} mapping L{bytes} to no-argument callable which
        returns L{ICredentials <twisted.cred.credentials.ICredentials>}
        subclass provider.
    @ivar challengers: A mapping of acceptable authorization mechanism to
        callable which creates credentials to use for authentication.
    """
    protocol = smtp.ESMTP
    context = None

    def __init__(self, *args):
        """
        @param args: Arguments for L{SMTPFactory.__init__}

        @see: L{SMTPFactory.__init__}
        """
        SMTPFactory.__init__(self, *args)
        self.challengers = {
            b'CRAM-MD5': CramMD5Credentials
        }


    def buildProtocol(self, addr):
        """
        Create an instance of an ESMTP server protocol.

        @type addr: L{IAddress <twisted.internet.interfaces.IAddress>} provider
        @param addr: The address of the ESMTP client.

        @rtype: L{ESMTP}
        @return: An ESMTP protocol.
        """
        p = SMTPFactory.buildProtocol(self, addr)
        p.challengers = self.challengers
        p.ctx = self.context
        return p



class VirtualPOP3(pop3.POP3):
    """
    A virtual hosting POP3 server.

    @type service: L{MailService}
    @ivar service: The email service that created this server.  This must be
        set by the service.

    @type domainSpecifier: L{bytes}
    @ivar domainSpecifier: The character to use to split an email address into
        local-part and domain. The default is '@'.
    """
    service = None

    domainSpecifier = '@' # Gaagh! I hate POP3. No standardized way
                          # to indicate user@host. '@' doesn't work
                          # with NS, e.g.

    def authenticateUserAPOP(self, user, digest):
        """
        Perform APOP authentication.

        Override the default lookup scheme to allow virtual domains.

        @type user: L{bytes}
        @param user: The name of the user attempting to log in.

        @type digest: L{bytes}
        @param digest: The challenge response.

        @rtype: L{Deferred} which successfully results in 3-L{tuple} of
            (L{IMailbox <pop3.IMailbox>}, L{IMailbox <pop3.IMailbox>}
            provider, no-argument callable)
        @return: A deferred which fires when authentication is complete.
            If successful, it returns an L{IMailbox <pop3.IMailbox>} interface,
            a mailbox and a logout function. If authentication fails, the
            deferred fails with an L{UnauthorizedLogin
            <twisted.cred.error.UnauthorizedLogin>} error.
        """
        user, domain = self.lookupDomain(user)
        try:
            portal = self.service.lookupPortal(domain)
        except KeyError:
            return defer.fail(UnauthorizedLogin())
        else:
            return portal.login(
                pop3.APOPCredentials(self.magic, user, digest),
                None,
                pop3.IMailbox
            )


    def authenticateUserPASS(self, user, password):
        """
        Perform authentication for a username/password login.

        Override the default lookup scheme to allow virtual domains.

        @type user: L{bytes}
        @param user: The name of the user attempting to log in.

        @type password: L{bytes}
        @param password: The password to authenticate with.

        @rtype: L{Deferred} which successfully results in 3-L{tuple} of
            (L{IMailbox <pop3.IMailbox>}, L{IMailbox <pop3.IMailbox>}
            provider, no-argument callable)
        @return: A deferred which fires when authentication is complete.
            If successful, it returns an L{IMailbox <pop3.IMailbox>} interface,
            a mailbox and a logout function. If authentication fails, the
            deferred fails with an L{UnauthorizedLogin
            <twisted.cred.error.UnauthorizedLogin>} error.
        """
        user, domain = self.lookupDomain(user)
        try:
            portal = self.service.lookupPortal(domain)
        except KeyError:
            return defer.fail(UnauthorizedLogin())
        else:
            return portal.login(
                UsernamePassword(user, password),
                None,
                pop3.IMailbox
            )


    def lookupDomain(self, user):
        """
        Check whether a domain is among the virtual domains supported by the
        mail service.

        @type user: L{bytes}
        @param user: An email address.

        @rtype: 2-L{tuple} of (L{bytes}, L{bytes})
        @return: The local part and the domain part of the email address if the
            domain is supported.

        @raise POP3Error: When the domain is not supported by the mail service.
        """
        try:
            user, domain = user.split(self.domainSpecifier, 1)
        except ValueError:
            domain = ''
        if domain not in self.service.domains:
             raise pop3.POP3Error("no such domain %s" % domain)
        return user, domain



class POP3Factory(protocol.ServerFactory):
    """
    A POP3 server protocol factory.

    @ivar service: See L{__init__}

    @type protocol: no-argument callable which returns a L{Protocol
        <protocol.Protocol>} subclass
    @ivar protocol: A callable which creates a protocol.  The default value is
        L{VirtualPOP3}.
    """
    protocol = VirtualPOP3
    service = None

    def __init__(self, service):
        """
        @type service: L{MailService}
        @param service: An email service.
        """
        self.service = service


    def buildProtocol(self, addr):
        """
        Create an instance of a POP3 server protocol.

        @type addr: L{IAddress <twisted.internet.interfaces.IAddress>} provider
        @param addr: The address of the POP3 client.

        @rtype: L{POP3}
        @return: A POP3 protocol.
        """
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.service = self.service
        return p
