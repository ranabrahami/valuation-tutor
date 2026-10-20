"""About and privacy: who this is for, what is stored, and deleting your data."""

import shared
import streamlit as st
import ui


def render() -> None:
    b = shared.load()
    t = b.t
    with st.columns([5, 4])[0]:
        ui.brand(t.t("app.title"))
    st.html(ui.crumb_title(t.t("about.eyebrow"), t.t("about.title")) + ui.lead(t.t("about.intro")))
    with st.container(key="card_privacy"):
        st.html(ui.prompt(t.t("about.privacy_title")) + "".join(
            f'<p class="rn-lead" style="font-size:.97rem">{t.t(f"about.privacy_{i}")}</p>' for i in range(1, 6)))
        acct = shared.account()
        if acct:
            if st.button(t.t("about.delete"), icon=":material/delete:", key="delete_me"):
                st.session_state.confirm_delete = True
            if st.session_state.get("confirm_delete"):
                st.warning(t.t("about.delete_confirm"))
                c = st.columns(4)
                if c[0].button(t.t("about.delete_yes"), type="primary", key="delete_yes"):
                    shared.store().delete_learner(acct["id"])
                    for k in ("learner", "learner_owner", "saved_digest", "activity", "confirm_delete"):
                        st.session_state.pop(k, None)
                    st.logout()
                if c[1].button(t.t("about.delete_no"), key="delete_no"):
                    st.session_state.confirm_delete = False
                    st.rerun()
    st.write("")
    with st.container(key="card_disclaimer"):
        st.html(ui.feedback("info", t.t("about.disclaimer_title"), t.t("app.not_advice") + " "
                            + t.t("app.data_as_of", date=next(iter(b.sectors.values())).data_as_of,
                                  standard=next(iter(b.sectors.values())).accounting_standard)))
