import os
import stat
import sys
from P4 import P4, P4Exception
from PySide2.QtWidgets import (
    QApplication, QFileDialog, QPushButton, QWidget, QVBoxLayout, QLabel, QTextEdit
)
from PySide2.QtGui import QFont
from PySide2.QtCore import Qt

# Function to remove read-only attribute from a file
def unset_readonly(file_path):
    file_permissions = os.stat(file_path).st_mode
    if not file_permissions & stat.S_IWRITE:
        os.chmod(file_path, stat.S_IWRITE)

# Function to convert a local file path to a Perforce depot path
def local_to_perforce_path(local_path):
    # Remove the drive letter and Perforce root from the local path
    drive, tail = os.path.splitdrive(local_path)
    # Find the index of "Potter" in the path and reconstruct the correct depot path
    index = tail.lower().find('potter')
    if index != -1:
        # Remove everything before and including 'Potter' and replace backslashes with forward slashes
        tail = tail[index:].replace('\\', '/')
    else:
        # If 'Potter' is not found, return the path unchanged (or raise an error if necessary)
        return local_path
    # Construct the correct depot path, starting with "//"
    depot_path = f"//{tail}"
    return depot_path


# Function to check out, clean, and submit a file via Perforce
def clean_ma_file(file_path, log_output):
    p4 = P4()
    try:
        # Connect to Perforce:
        p4Dict = p4.connect()
        if not p4Dict:
            log_output.append("Failed to connect to Perforce.")
            return
        
        # Convert local file path to Perforce depot path
        depot_path = local_to_perforce_path(file_path)
        log_output.append(f"Checking out file: {depot_path}")

        try:
            # Checkout the file from Perforce
            p4.run('edit', depot_path)
        except P4Exception as e:
            log_output.append(f"Error checking out file: {depot_path} {e}")
            return
        
        unset_readonly(file_path)

        # Read and clean the file
        with open(file_path, 'r') as file:
            lines = file.readlines()

        cleaned_lines = []
        skip_lines = 0
        modified = False

        for line in lines:
            # Detect the start of any vaccine_gene block
            if 'createNode script' in line and 'vaccine_gene' in line:
                skip_lines = 10  # We aim to skip up to 10 lines, but with conditions
                modified = True
                continue

            # Skip the required number of lines for vaccine_gene, but stop if conditions are met
            if skip_lines > 0:
                if not (line.strip().startswith(('addAttr', 'setAttr', '['))):
                    if 'createNode' not in line and 'breed_gene' not in line:
                        skip_lines = 0  # Stop skipping
                        cleaned_lines.append(line)
                        continue

                skip_lines -= 1
                continue

            cleaned_lines.append(line)

        # If changes were made, write the cleaned lines back to the file
        if modified:
            with open(file_path, 'w') as file:
                file.writelines(cleaned_lines)
            log_output.append(f"Cleaned: {file_path}")

            try:
                # Create a new changelist and add the file to it
                change = p4.fetch_change()
                change._description = 'Removed Vaccine virus from file'
                change._files = [depot_path]
                # Submit the changelist
                p4.run_submit(change)
                log_output.append(f"Submitted: {depot_path}")
            except P4Exception as e:
                log_output.append(f"Error submitting file: {depot_path} {e}")
                p4.run('revert', depot_path)  # Revert the file in case of an error
        else:
            log_output.append(f"No changes were made: {file_path}")

    except PermissionError as e:
        log_output.append(f"Error: {e} - Could not modify {file_path}")
        print(f"Error: {e} - Could not modify {file_path}")
    
    finally:
        if p4:
            p4.disconnect()

# Main widget to select and process files
class CleanerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Set up main layout
        layout = QVBoxLayout()

        # Header label
        self.header_label = QLabel("Maya File Cleaner", self)
        self.header_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.header_label)

        # Description label
        self.label = QLabel("Select or paste .ma files to clean:", self)
        self.label.setFont(QFont("Arial", 12))
        layout.addWidget(self.label)

        # Button to select files
        self.button = QPushButton("Select Files", self)
        self.button.setFont(QFont("Arial", 10))
        self.button.setStyleSheet("padding: 8px 16px; background-color: #3498db; color: white; border-radius: 5px;")
        self.button.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.button)

        # Text input area for pasting file paths
        self.path_input = QTextEdit(self)
        self.path_input.setPlaceholderText("Or paste file paths here (one per line)")
        self.path_input.setFont(QFont("Arial", 10))
        self.path_input.setStyleSheet("padding: 8px; border-radius: 5px; border: 1px solid #bdc3c7;")
        layout.addWidget(self.path_input)

        # Button to clean files
        self.clean_button = QPushButton("Clean Files", self)
        self.clean_button.setFont(QFont("Arial", 10))
        self.clean_button.setStyleSheet("padding: 8px 16px; background-color: #2ecc71; color: white; border-radius: 5px;")
        self.clean_button.clicked.connect(self.clean_pasted_files)
        layout.addWidget(self.clean_button)

        # Output log box to display progress and results
        self.log_output = QTextEdit(self)
        self.log_output.setFont(QFont("Courier", 10))
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("padding: 8px; border-radius: 5px; border: 1px solid #bdc3c7; background-color: black; color: white;")
        layout.addWidget(self.log_output)

        # Footer label to show status
        self.result_label = QLabel("", self)
        self.result_label.setFont(QFont("Arial", 10))
        self.result_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.result_label)

        # Add spacing and margin
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.setLayout(layout)
        self.setWindowTitle('Maya File Cleaner')
        self.setMinimumWidth(500)

    def open_file_dialog(self):
        # Get the current text in the box
        existing_paths = self.path_input.toPlainText().strip()

        # Open file dialog to select files
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Maya ASCII Files", "", "Maya ASCII Files (*.ma)")

        if file_paths:
            # Convert selected paths to a single string
            selected_paths = "\n".join(file_paths)

            # Append the selected paths to existing ones, if there are any
            if existing_paths:
                self.path_input.setPlainText(f"{existing_paths}\n{selected_paths}")
            else:
                self.path_input.setPlainText(selected_paths)

    def clean_pasted_files(self):
        # Clear previous log output
        self.log_output.clear()

        # Get the text from the input area
        pasted_text = self.path_input.toPlainText()

        # Split text into file paths by newlines
        file_paths = pasted_text.strip().split('\n')

        if not file_paths or file_paths == ['']:
            self.result_label.setText("No valid file paths provided.")
            self.result_label.setStyleSheet("color: red;")
        else:
            cleaned_count = 0
            for file_path in file_paths:
                file_path = file_path.strip()
                if os.path.exists(file_path) and file_path.endswith('.ma'):
                    clean_ma_file(file_path, self.log_output)
                    cleaned_count += 1
                else:
                    self.log_output.append(f"Invalid path: {file_path}")
                    print(f"Invalid path: {file_path}")
            self.result_label.setText(f"Processed {cleaned_count} files.")
            self.result_label.setStyleSheet("color: green;")

# Main entry point
def main():
    app = QApplication(sys.argv)
    cleaner = CleanerApp()
    cleaner.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
