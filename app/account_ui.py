"""Sign-in control. Hidden when sign-in isn't configured (then everyone plays as a guest)."""

import shared
import streamlit as st


def control(where) -> None:
    if not shared.auth_configured():
        return
    t = shared.load().t
    acct = shared.account()
    if acct:
        label = t.t("account.signed_in", name=acct["name"]) if acct["name"] else t.t("account.sign_out")
        if where.button(label, icon=":material/logout:", key="sign_out", help=t.t("account.sign_out"),
                        width="stretch"):
            st.logout()
    elif where.button(t.t("account.sign_in"), icon=":material/login:", key="sign_in", type="primary",
                      help=t.t("account.sign_in_help"), width="stretch"):
        st.login("google")
