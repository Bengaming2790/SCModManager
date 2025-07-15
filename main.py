import os
import platform
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, Scrollbar, simpledialog
import tkinter.ttk as ttk
import requests
from packaging.version import parse as parse_version
import zipfile
import io

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller extracts files to this temp folder
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# --- Paths ---

def get_minecraft_folder():
    system = platform.system()
    if system == "Windows":
        appdata = os.getenv("APPDATA")
        return os.path.join(appdata, ".minecraft")
    elif system == "Darwin":
        home = os.path.expanduser("~")
        return os.path.join(home, "Library", "Application Support", "minecraft")
    elif system == "Linux":
        home = os.path.expanduser("~")
        return os.path.join(home, ".minecraft")
    else:
        raise Exception("Unsupported OS")

MC_FOLDER = get_minecraft_folder()
MODS_FOLDER = os.path.join(MC_FOLDER, "mods")
SHADERPACKS_FOLDER = os.path.join(MC_FOLDER, "shaderpacks")
RESOURCEPACKS_FOLDER = os.path.join(MC_FOLDER, "resourcepacks")

PROFILE_FOLDER = "profiles"
SHADERPACK_PROFILE_FOLDER = "shaderpack_profiles"
RESOURCEPACK_PROFILE_FOLDER = "resourcepack_profiles"

# --- Utility functions ---

def get_profiles_in(folder):
    if not os.path.exists(folder):
        return []
    return [name for name in os.listdir(folder) if os.path.isdir(os.path.join(folder, name))]

def clear_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    else:
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"Failed to delete {item_path}: {e}")

def copy_profile_files(src_folder, dst_folder):
    os.makedirs(dst_folder, exist_ok=True)
    for item in os.listdir(src_folder):
        source_path = os.path.join(src_folder, item)
        dest_path = os.path.join(dst_folder, item)
        try:
            if os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path)
            elif os.path.isdir(source_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(source_path, dest_path)
        except Exception as e:
            print(f"Failed to copy {source_path} to {dest_path}: {e}")



def search_modrinth_mods(query):
    url = "https://api.modrinth.com/v2/search"
    params = {
        "query": query,
        "facets": ["versions:"],  # can filter by Minecraft version if you want
        "index": 0,
        "limit": 5
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception("Modrinth API error")
    data = response.json()
    return data["hits"]  # list of mod projects

def download_modrinth_mod_file(mod_id, profile_folder):
    # Get versions
    versions_url = f"https://api.modrinth.com/v2/project/{mod_id}/version"
    response = requests.get(versions_url)
    response.raise_for_status()
    versions = response.json()

    # Pick latest stable version (simple example: just take first)
    latest_version = versions[0]
    files = latest_version.get("files", [])
    if not files:
        raise Exception("No files found for this version")
    # Download the first file
    file_url = files[0]["url"]
    file_name = files[0]["filename"]

    response = requests.get(file_url, stream=True)
    response.raise_for_status()

    os.makedirs(profile_folder, exist_ok=True)
    file_path = os.path.join(profile_folder, file_name)

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return file_path



# --- GUI Setup ---

root = tk.Tk()
root.geometry("600x720")
root.title("ScrubCraft Modding Manager")

icon_path = resource_path("icon.png")
try:
    icon = tk.PhotoImage(file=icon_path)
    root.iconphoto(True, icon)
except Exception as e:
    print(f"Failed to load icon: {e}")


try:
    icon = tk.PhotoImage(file="icon.png")
    root.iconphoto(True, icon)
except Exception:
    pass

# --- Variables ---

mod_selected_profile = tk.StringVar(root)
shader_selected_profile = tk.StringVar(root)
resource_selected_profile = tk.StringVar(root)

# --- Functions for mods ---

def refresh_mod_profiles():
    profiles = get_profiles_in(PROFILE_FOLDER)
    menu = mod_profile_dropdown["menu"]
    menu.delete(0, "end")
    if profiles:
        for p in profiles:
            menu.add_command(label=p, command=lambda value=p: mod_selected_profile.set(value))
        mod_selected_profile.set(profiles[0])
    else:
        menu.add_command(label="No Profiles", command=lambda: mod_selected_profile.set("No Profiles"))
        mod_selected_profile.set("No Profiles")

def create_mod_profile():
    profile_name = mod_profile_name_entry.get().strip()
    if not profile_name:
        messagebox.showwarning("Input Error", "Please enter a mod profile name.")
        return
    path = os.path.join(PROFILE_FOLDER, profile_name)
    try:
        os.makedirs(path, exist_ok=True)
        messagebox.showinfo("Success", f"Mod profile created:\n{path}")
        refresh_mod_profiles()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create mod profile:\n{e}")

def import_mod_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Mod Files (.jar)",
        filetypes=[("Java Mod Files", "*.jar")]
    )
    if not file_paths:
        return

    selected = mod_selected_profile.get()
    if selected == "No Profiles":
        messagebox.showwarning("No Profile Selected", "Please create and select a mod profile first.")
        return

    destination_folder = os.path.join(PROFILE_FOLDER, selected)
    os.makedirs(destination_folder, exist_ok=True)
    try:
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            shutil.copy(file_path, os.path.join(destination_folder, file_name))
        messagebox.showinfo("Success", f"Imported {len(file_paths)} files to mod profile '{selected}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import mod files:\n{e}")

def apply_mod_profile():
    selected = mod_selected_profile.get()
    if selected == "No Profiles":
        messagebox.showwarning("No Profile Selected", "Please create and select a mod profile first.")
        return

    profile_path = os.path.join(PROFILE_FOLDER, selected)
    if not os.path.exists(profile_path):
        messagebox.showerror("Error", f"Mod profile folder does not exist:\n{profile_path}")
        return

    try:
        clear_folder(MODS_FOLDER)
        copy_profile_files(profile_path, MODS_FOLDER)
        messagebox.showinfo("Success", f"Applied mod profile '{selected}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply mod profile:\n{e}")

# --- Functions for shaderpacks ---

def refresh_shader_profiles():
    profiles = get_profiles_in(SHADERPACK_PROFILE_FOLDER)
    menu = shader_profile_dropdown["menu"]
    menu.delete(0, "end")
    if profiles:
        for p in profiles:
            menu.add_command(label=p, command=lambda value=p: shader_selected_profile.set(value))
        shader_selected_profile.set(profiles[0])
    else:
        menu.add_command(label="No Profiles", command=lambda: shader_selected_profile.set("No Profiles"))
        shader_selected_profile.set("No Profiles")

def create_shader_profile():
    profile_name = shader_profile_name_entry.get().strip()
    if not profile_name:
        messagebox.showwarning("Input Error", "Please enter a shaderpack profile name.")
        return
    path = os.path.join(SHADERPACK_PROFILE_FOLDER, profile_name)
    try:
        os.makedirs(path, exist_ok=True)
        messagebox.showinfo("Success", f"Shaderpack profile created:\n{path}")
        refresh_shader_profiles()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create shaderpack profile:\n{e}")

def import_shader_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Shaderpack Files (.zip)",
        filetypes=[("Zip Files", "*.zip"), ("All Files", "*.*")]
    )
    if not file_paths:
        return

    selected = shader_selected_profile.get()
    if selected == "No Profiles":
        messagebox.showwarning("No Profile Selected", "Please create and select a shader profile first.")
        return

    destination_folder = os.path.join(SHADERPACK_PROFILE_FOLDER, selected)
    os.makedirs(destination_folder, exist_ok=True)
    try:
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            shutil.copy(file_path, os.path.join(destination_folder, file_name))
        messagebox.showinfo("Success", f"Imported {len(file_paths)} files to shader profile '{selected}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import shaderpack files:\n{e}")

def apply_shader_profile():
    selected = shader_selected_profile.get()
    if selected == "No Profiles":
        messagebox.showwarning("No Profile Selected", "Please create and select a shader profile first.")
        return

    profile_path = os.path.join(SHADERPACK_PROFILE_FOLDER, selected)
    if not os.path.exists(profile_path):
        messagebox.showerror("Error", f"Shader profile folder does not exist:\n{profile_path}")
        return

    try:
        clear_folder(SHADERPACKS_FOLDER)
        copy_profile_files(profile_path, SHADERPACKS_FOLDER)
        messagebox.showinfo("Success", f"Applied shader profile '{selected}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply shader profile:\n{e}")

# --- Functions for resourcepacks ---

def refresh_resource_profiles():
    profiles = get_profiles_in(RESOURCEPACK_PROFILE_FOLDER)
    menu = resource_profile_dropdown["menu"]
    menu.delete(0, "end")
    if profiles:
        for p in profiles:
            menu.add_command(label=p, command=lambda value=p: resource_selected_profile.set(value))
        resource_selected_profile.set(profiles[0])
    else:
        menu.add_command(label="No Profiles", command=lambda: resource_selected_profile.set("No Profiles"))
        resource_selected_profile.set("No Profiles")

def create_resource_profile():
    profile_name = resource_profile_name_entry.get().strip()
    if not profile_name:
        messagebox.showwarning("Input Error", "Please enter a resourcepack profile name.")
        return
    path = os.path.join(RESOURCEPACK_PROFILE_FOLDER, profile_name)
    try:
        os.makedirs(path, exist_ok=True)
        messagebox.showinfo("Success", f"Resourcepack profile created:\n{path}")
        refresh_resource_profiles()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create resourcepack profile:\n{e}")

def import_resource_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Resourcepack Files (.zip or folder)",
        filetypes=[("Zip Files", "*.zip"), ("All Files", "*.*")]
    )
    if not file_paths:
        return

    selected = resource_selected_profile.get()
    if selected == "No Profiles":
        messagebox.showwarning("No Profile Selected", "Please create and select a resource profile first.")
        return

    destination_folder = os.path.join(RESOURCEPACK_PROFILE_FOLDER, selected)
    os.makedirs(destination_folder, exist_ok=True)
    try:
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            shutil.copy(file_path, os.path.join(destination_folder, file_name))
        messagebox.showinfo("Success", f"Imported {len(file_paths)} files to resource profile '{selected}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import resourcepack files:\n{e}")

def apply_resource_profile():
    selected = resource_selected_profile.get()
    if selected == "No Profiles":
        messagebox.showwarning("No Profile Selected", "Please create and select a resource profile first.")
        return

    profile_path = os.path.join(RESOURCEPACK_PROFILE_FOLDER, selected)
    if not os.path.exists(profile_path):
        messagebox.showerror("Error", f"Resource profile folder does not exist:\n{profile_path}")
        return

    try:
        clear_folder(RESOURCEPACKS_FOLDER)
        copy_profile_files(profile_path, RESOURCEPACKS_FOLDER)
        messagebox.showinfo("Success", f"Applied resource profile '{selected}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply resource profile:\n{e}")

# --- Layout ---

def section_label(text):
    lbl = tk.Label(root, text=text, font=("Arial", 16, "bold"))
    lbl.pack(pady=(20, 5))




#Extra Menu for Modrinth integration
def open_modrinth_window():
    def search_mods():
        query = search_entry.get().strip()
        if not query:
            messagebox.showwarning("Input Error", "Please enter a search term.")
            return

        selected_loader = loader_var.get()
        selected_version = version_var.get()

        listbox.delete(0, tk.END)
        mods.clear()

        try:
            response = requests.get("https://api.modrinth.com/v2/search", params={"query": query, "limit": 20})
            response.raise_for_status()
            data = response.json()

            for mod in data["hits"]:
                mod_id = mod["project_id"]
                # Fetch versions for this mod
                version_res = requests.get(f"https://api.modrinth.com/v2/project/{mod_id}/version")
                version_res.raise_for_status()
                versions = version_res.json()

                # Check if any version matches filters
                matching_versions = [
                    v for v in versions
                    if selected_loader in v.get("loaders", [])
                       and selected_version in v.get("game_versions", [])
                ]

                if matching_versions:
                    mods.append((mod["title"], mod_id))
                    listbox.insert(tk.END, mod["title"])

            if not mods:
                messagebox.showinfo("No Mods Found",
                                    f"No mods found for loader '{selected_loader}' and version '{selected_version}'.")

        except Exception as e:
            messagebox.showerror("API Error", f"Failed to fetch mods:\n{e}")

    def download_selected():
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a mod to download.")
            return

        index = selection[0]
        mod_name, mod_id = mods[index]

        selected_loader = loader_var.get()
        selected_version = version_var.get()

        try:
            version_res = requests.get(f"https://api.modrinth.com/v2/project/{mod_id}/version")
            version_res.raise_for_status()
            versions = version_res.json()

            # Filter by selected loader and game version
            matching_versions = [
                v for v in versions
                if selected_loader in v.get("loaders", [])
                and selected_version in v.get("game_versions", [])
            ]

            if not matching_versions:
                raise Exception(f"No matching versions for loader '{selected_loader}' and Minecraft '{selected_version}'.")

            file_info = matching_versions[0]["files"][0]
            download_url = file_info["url"]
            file_name = file_info["filename"]

            profile_name = simpledialog.askstring("Choose Profile", "Enter the profile name to download this mod into:")
            if not profile_name:
                return

            dest_folder = os.path.join(PROFILE_FOLDER, profile_name)
            os.makedirs(dest_folder, exist_ok=True)

            file_path = os.path.join(dest_folder, file_name)
            with open(file_path, "wb") as f:
                file_data = requests.get(download_url)
                f.write(file_data.content)

            messagebox.showinfo("Success", f"Downloaded '{file_name}' to profile '{profile_name}'")

        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to download mod:\n{e}")

    # Fetch Minecraft release versions (excluding snapshots) and sort properly
    try:
        ver_response = requests.get("https://api.modrinth.com/v2/tag/game_version")
        ver_response.raise_for_status()
        all_versions = ver_response.json()
        version_options = [
            v["version"] for v in all_versions if v.get("version_type") == "release"
        ]
        version_options = sorted(version_options, key=parse_version, reverse=True)
    except Exception as e:
        messagebox.showerror("Version Fetch Error", f"Could not fetch Minecraft versions:\n{e}")
        version_options = ["1.21.5", "1.20.1"]

    # Mod Loader options
    loader_options = ["fabric", "forge", "neoforge", "quilt"]

    mod_window = tk.Toplevel()
    mod_window.title("Search Modrinth Mods")
    mod_window.geometry("420x520")

    search_entry = tk.Entry(mod_window, width=30)
    search_entry.pack(pady=5)

    search_btn = tk.Button(mod_window, text="Search", command=search_mods)
    search_btn.pack(pady=5)

    # Mod Loader Dropdown
    tk.Label(mod_window, text="Select Mod Loader").pack()
    loader_var = tk.StringVar(value=loader_options[0])
    loader_dropdown = tk.OptionMenu(mod_window, loader_var, *loader_options)
    loader_dropdown.pack(pady=5)

    # Minecraft Version Combobox with scrollable dropdown, showing 15 at a time
    tk.Label(mod_window, text="Select Minecraft Version").pack()
    version_var = tk.StringVar(value=version_options[0])
    version_combobox = ttk.Combobox(mod_window, textvariable=version_var, values=version_options, height=15)
    version_combobox.pack(pady=5)
    version_combobox.state(["readonly"])  # Make it readonly dropdown

    # Mod list
    list_frame = tk.Frame(mod_window)
    list_frame.pack(expand=True, fill=tk.BOTH, pady=5)

    scrollbar = Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = Listbox(list_frame, yscrollcommand=scrollbar.set)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    download_btn = tk.Button(mod_window, text="Download to Profile", command=download_selected)
    download_btn.pack(pady=10)

    mods = []

# Mods UI
section_label("Mod Profiles")

mod_profiles = get_profiles_in(PROFILE_FOLDER)
if mod_profiles:
    mod_options = mod_profiles
else:
    mod_options = ["No Profiles"]
    mod_selected_profile.set("No Profiles")
mod_profile_dropdown = tk.OptionMenu(root, mod_selected_profile, *mod_options)
mod_profile_dropdown.pack()

mod_profile_name_entry = tk.Entry(root)
mod_profile_name_entry.pack(pady=5)

mod_create_profile_button = tk.Button(root, text="Create Mod Profile", command=create_mod_profile)
mod_create_profile_button.pack()

mod_import_button = tk.Button(root, text="Import Mods (.jar)", command=import_mod_files)
mod_import_button.pack(pady=5)

mod_apply_button = tk.Button(root, text="Apply Mod Profile", command=apply_mod_profile)
mod_apply_button.pack()

# Shaderpacks UI
section_label("Shaderpack Profiles")

shader_profiles = get_profiles_in(SHADERPACK_PROFILE_FOLDER)
if shader_profiles:
    shader_options = shader_profiles
else:
    shader_options = ["No Profiles"]
    shader_selected_profile.set("No Profiles")
shader_profile_dropdown = tk.OptionMenu(root, shader_selected_profile, *shader_options)
shader_profile_dropdown.pack()

shader_profile_name_entry = tk.Entry(root)
shader_profile_name_entry.pack(pady=5)

shader_create_profile_button = tk.Button(root, text="Create Shader Profile", command=create_shader_profile)
shader_create_profile_button.pack()

shader_import_button = tk.Button(root, text="Import Shaderpack Files (.zip)", command=import_shader_files)
shader_import_button.pack(pady=5)

shader_apply_button = tk.Button(root, text="Apply Shader Profile", command=apply_shader_profile)
shader_apply_button.pack()

# Resourcepacks UI
section_label("Resourcepack Profiles")

resource_profiles = get_profiles_in(RESOURCEPACK_PROFILE_FOLDER)
if resource_profiles:
    resource_options = resource_profiles
else:
    resource_options = ["No Profiles"]
    resource_selected_profile.set("No Profiles")
resource_profile_dropdown = tk.OptionMenu(root, resource_selected_profile, *resource_options)
resource_profile_dropdown.pack()

resource_profile_name_entry = tk.Entry(root)
resource_profile_name_entry.pack(pady=5)

resource_create_profile_button = tk.Button(root, text="Create Resource Profile", command=create_resource_profile)
resource_create_profile_button.pack()

resource_import_button = tk.Button(root, text="Import Resourcepack Files (.zip)", command=import_resource_files)
resource_import_button.pack(pady=5)

resource_apply_button = tk.Button(root, text="Apply Resource Profile", command=apply_resource_profile)
resource_apply_button.pack()

open_button = tk.Button(root, text="Search Modrinth", command=open_modrinth_window)
open_button.pack(pady=30)
open_mods_button = tk.Button(root, text="Official Modpacks", command=open_modpack_window)
open_mods_button.pack(pady=30)

root.mainloop()