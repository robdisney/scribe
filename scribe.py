""" Use this version if using api key from OpenAI """

# jarvis.py

# Import libraries
import subprocess
import os
from datetime import datetime
from pathlib import Path
import openai
import re
import shutil

client = OpenAI(api_key="<your_key_here>")

# Function to check and create directory if not exists, and clear it if it does
def check_and_create_dir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    else:
        # If the directory exists, clear its contents
        for filename in os.listdir(dir_name):
            file_path = os.path.join(dir_name, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

# Function to check and create directory if not exists for scripts
def check_and_create_dir_scripts(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# Call the function for 'scripts' and 'results' directories
check_and_create_dir('drafts')
check_and_create_dir('results')
check_and_create_dir_scripts('scripts')

# Initialize lists to store the drafts and results
drafts_and_results_list = []

# Define function to extract python code from responses
def extract_python(response_content):
    # Define the regular expression pattern for extracting Python code blocks
    pattern = r"```python(.*?)```"
    # Use re.DOTALL to make the dot match newlines as well
    match = re.search(pattern, response_content, re.DOTALL)
    if match:
        # Extract the code, remove leading/trailing whitespace, and return
        return match.group(1).strip()
    elif 'satisfied' in response_content.lower():
        return 'satisfied'
    else:
        return None
    
# Define the function to extract any "pip install" statement from chatgpt response and then install via subprocess before attempting running python script.
def handle_pip_install(response_content):
    # Define the regular expression pattern for extracting pip install commands
    pattern = r"pip install (.*?)\n"
    match = re.search(pattern, response_content, re.DOTALL)
    if match:
        # Extract the command, remove leading/trailing whitespace, and return
        command = match.group(1).strip()
        command = "pip install " + command
        print(f"Executing '''bash\n{command}\n'''")
        # Use subprocess to execute the command
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        # Fetch the output and errors, if any
        output, error = process.communicate()
        # Print the command's output
        print('Output:', output.decode())
        # Print the command's error
        if error:
            print('Error:', error.decode())

# Define the function to generate a response from the AI
def generate_response(prompt):
    response = client.chat.completions.create(messages=[{"role": "user", "content": prompt}],
                                              model="gpt-4-1106-preview", # CHANGE MODEL TO SUIT YOUR NEEDS
                                              max_tokens=4000,
                                              temperature=0.75)
    return response.choices[0].message.content

# Function to read the latest prompt and append the additional phrase
def read_latest_prompt():
    prompt_content = Path('jprompt.txt').read_text('utf-8')
    additional_phrase = "\nReturn your response as a complete python script. The code you return must be a complete solution. Ensure that if you use print statements, they are not commented out, regardless of the original prompt request."
    return f"{prompt_content}{additional_phrase}"

# Function to write the Python script to a file
def write_draft_to_file(script, version):
    filename = f'drafts/draft_v{version}.py'
    with open(filename, 'w') as file:
        file.write(script)
    return filename

# Function to execute the Python script and capture its output
def execute_script(filename):
    try:
        result = subprocess.run(['python', filename], capture_output=True, text=True, check=True)
        return result.stdout, None
    except subprocess.CalledProcessError as e:
        # Return both stdout and stderr if an error occurs
        return e.stdout, e.stderr

# Function to write the result to a file with a timestamp
def write_result_to_file(output):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'results/results_{timestamp}.txt'
    with open(filename, 'w') as file:
        file.write(output)
    return filename, timestamp

def write_final_version_to_file(script):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'scripts/script_{timestamp}.py'
    with open(filename, 'w') as file:
        file.write(script)
    return filename, timestamp

# Main loop for generating, executing, and validating the script
def main_loop():
    version = 1
    original_prompt = read_latest_prompt()

    while True:
        # Generate the response from AI
        prompt = original_prompt if version == 1 else combined_prompt
        print(f'sending prompt to chatgpt iteration {version}')
        response = generate_response(prompt)
        print(f"ChatGPT's response for iteration {version} is: \n", response)

        # Handle pip install commands in the response
        handle_pip_install(response)

        # Check if AI is satisfied or if there's a Python script to extract
        extracted_code = extract_python(response)
        print('extracted code:\n', extracted_code)
        if extracted_code == 'satisfied':
            print("AI is satisfied with the script.")
            final_version=write_final_version_to_file(most_recent_version)
            break
        elif extracted_code is None:
            print("No Python script found in AI response.")
            continue  # Continue to the next iteration instead of breaking

        # Write the new script version
        script_filename = write_draft_to_file(extracted_code, version)
        print(f"Script version {version} written to {script_filename}.")

        # Execute the new script version
        output, error = execute_script(script_filename)
        execution_outcome = output, error

        # Write the output or error to a timestamped results file
        if error:
            result_filename, _ = write_result_to_file(f"Error executing script:\n{error}")
            print(f"Error executing script: Check {result_filename} for details.")
        else:
            result_filename, _ = write_result_to_file(output)
            print(f"Script version {version} executed. Check {result_filename} for the output.")

        # Append the script and result to their respective lists
        current_version = script_filename + "\n" + extracted_code + "\n" + result_filename + "\n" + str(execution_outcome)
        drafts_and_results_list.append(current_version)
        print("### drafts_and_results_list:\n\n", drafts_and_results_list)
        #last_three_drafts_and_results = "\n".join(drafts_and_results_list[-3:])
        #print("### last_three_drafts_and_results: \n\n" + last_three_drafts_and_results)
        # Prepare the prompt for the next iteration
        combined_prompt = f"You were asked: {original_prompt}\n\n# and produced these scripts and their respective results:\n{drafts_and_results_list[-3:]}\n\nBased on what you were asked to do, the scripts you wrote, and their results, are you satisfied? If yes, return only the word 'satisfied'. If no, revise the script to achieve the desired results. in your response, return the entire revised script.  If your code requires any libaries that need to be installed for the code to work, include a single 'pip install' command to install them."
        print(f"Sending the following prompt to AI:\n{combined_prompt}")
        most_recent_version = extracted_code
        version += 1

# Run the main loop
if __name__ == "__main__":
    main_loop()
