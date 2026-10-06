"""Users & Roles page — Admin only."""
from __future__ import annotations

import streamlit as st

from core.auth import current_user, require_role, hash_password
from core.db import list_users, create_user, update_user_role, deactivate_user
from core.audit import log_audit
from ui.components import page_header, relative_time, empty_state
from ui.theme import TOKENS


ROLES = ["admin", "officer", "citizen"]


def render() -> None:
    require_role(["admin"])
    user = current_user()

    page_header("Users & Roles", "Manage accounts, roles, and access.")

    tab_list, tab_create = st.tabs(["All Users", "Create User"])

    with tab_list:
        try:
            users = list_users(user)
        except PermissionError as e:
            st.error(str(e))
            return

        if not users:
            empty_state("No users", "Create the first user below.")
        else:
            # Header
            h1, h2, h3, h4, h5 = st.columns([1.5, 2, 1.5, 1.5, 2])
            for col, label in zip([h1, h2, h3, h4, h5], ["Username", "Name", "Role", "Status", "Actions"]):
                with col:
                    st.markdown(
                        f'<div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
                        f'text-transform:uppercase;padding:4px 0;border-bottom:2px solid {TOKENS["border"]}">'
                        f'{label}</div>',
                        unsafe_allow_html=True,
                    )

            for u in users:
                c1, c2, c3, c4, c5 = st.columns([1.5, 2, 1.5, 1.5, 2])
                with c1:
                    st.markdown(f'<span style="font-size:13px;font-weight:600">{u["username"]}</span>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'<span style="font-size:13px">{u["name"]}</span>', unsafe_allow_html=True)
                with c3:
                    new_role = st.selectbox(
                        "Role",
                        ROLES,
                        index=ROLES.index(u["role"]) if u["role"] in ROLES else 0,
                        key=f"role_sel_{u['id']}",
                        label_visibility="collapsed",
                    )
                    if new_role != u["role"]:
                        if st.button("Save", key=f"save_role_{u['id']}"):
                            try:
                                update_user_role(user, u["id"], new_role)
                                log_audit(user["username"], user["role"], "role_change", None,
                                          f"{u['username']} → {new_role}")
                                st.success(f"Role updated.")
                                st.rerun()
                            except PermissionError as e:
                                st.error(str(e))
                with c4:
                    active_text = "Active" if u["active"] else "Inactive"
                    active_color = TOKENS["low"] if u["active"] else TOKENS["muted"]
                    st.markdown(
                        f'<span style="font-size:12px;font-weight:600;color:{active_color}">{active_text}</span>',
                        unsafe_allow_html=True,
                    )
                with c5:
                    if u["username"] != user["username"] and u["active"]:
                        if st.button(
                            "Deactivate",
                            key=f"deact_{u['id']}",
                        ):
                            try:
                                deactivate_user(user, u["id"])
                                log_audit(user["username"], user["role"], "deactivate", None,
                                          f"Deactivated {u['username']}")
                                st.success(f"{u['username']} deactivated.")
                                st.rerun()
                            except PermissionError as e:
                                st.error(str(e))

                st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]}"></div>', unsafe_allow_html=True)

    with tab_create:
        st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:1rem">Create New User</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            new_username = st.text_input("Username", key="nu_username")
            new_name = st.text_input("Full name", key="nu_name")
        with c2:
            new_password = st.text_input("Password", type="password", key="nu_password")
            new_role = st.selectbox("Role", ROLES, key="nu_role")

        if st.button("Create User", key="create_user_btn"):
            if not new_username or not new_name or not new_password:
                st.error("All fields are required.")
            else:
                try:
                    uid = create_user(user, new_username.strip(), new_name.strip(),
                                      hash_password(new_password), new_role)
                    log_audit(user["username"], user["role"], "create_user", None,
                              f"Created user {new_username} with role {new_role}")
                    st.success(f"User '{new_username}' created (ID: {uid}).")
                    st.rerun()
                except PermissionError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Failed to create user: {e}")
