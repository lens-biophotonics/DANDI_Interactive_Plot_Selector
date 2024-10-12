##################### Libraries

# dandi
from dandi.dandiapi import DandiAPIClient 
# panda
import pandas as pd
# bokeh
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource, TapTool, CustomJS, HoverTool
from bokeh.io import output_notebook, output_file
from bokeh.transform import factor_cmap
from bokeh.palettes import Category20, Category10
# pickle
import pickle 
 # os
import os
# json
import json 
# urllib
from urllib.parse import quote
# jinja2
from jinja2 import Environment, FileSystemLoader 



##################### Helper Functions

######################## Section: 1. Data Gathering ########################


def extract_subject_from_path(path_parts):
    """
    Extract the subject ID from the parts of the path if the directory contains 'sub-' (subject identifier).
    Assumes the path follows a structure where subject IDs are in directories like 'sub-01', 'sub-02', etc.

    Args:
        path_parts (list): List of directory and file parts obtained from splitting the path by '/'.

    Returns:
        str: Subject ID if found, otherwise None.
    """
    for val in path_parts[:-1]:  # Loop through all parts except the last (which is usually the file name)
        if val.startswith("sub-"):  # Check if part starts with 'sub-'
            return val.split("sub-")[1]  # Return the part after 'sub-'
    return None  # If no 'sub-' part found, return None


def parse_asset_filename(assetname):
    """
    Extract key-value pairs from the asset file name. The file name parts are assumed to follow
    a 'key-value' format, where the key and value are separated by a hyphen (e.g., 'sub-01', 'task-rest').
    
    Args:
        assetname (str): The file name of the asset.
    
    Returns:
        dict: A dictionary of key-value pairs extracted from the file name.
    """
    return {
        key_value.split("-")[0]: "-".join(key_value.split("-")[1:])  # Split key-value pairs by '-'
        for key_value in assetname.split(".")[0].split("_")  # First, remove the file extension, then split by '_'
        if "-" in key_value  # Only keep parts that contain a '-'
    }


def extract_modality_from_filename(assetname, assetpath):
    """
    Extract the modality information from the file name. The modality usually appears at the end
    of the file name, separated by underscores (e.g., 'sub-01_task-rest_bold.nii' -> 'bold').

    Args:
        assetname (str): The name of the file.
        assetpath (str): The full path of the asset.

    Returns:
        str: The modality if found, otherwise None.
    """
    if "_" in assetname and "sub-" in assetname:  # Check if the file name follows the expected format
        # Extract everything after 'sub-' and split by '/'
        path = "sub-".join(assetpath.split("sub-")[1:])
        if len(path.split("/")) > 1:  # If there are multiple parts in the path, assume it's valid
            return assetname.split("_")[-1].split(".")[0]  # Extract modality from the last part of the name
    return None  # Return None if no modality found


def assets_to_df(ds):
    """
    Convert assets from a dandiset into a structured pandas DataFrame with extracted metadata.

    Args:
        ds: The dandiset object obtained from the Dandi API.

    Returns:
        df (pandas.DataFrame): A DataFrame containing information about each asset.
        assets (list): A list of asset objects from the dandiset.
    """
    # Get the list of assets from the dataset
    assets = list(ds.get_assets())
    
    # Initialize an empty list to store metadata for each asset
    asset_info = []
    
    # Loop through each asset in the list
    for asset in assets:
        # Split the asset's path into parts (directories and file name)
        path_parts = asset.path.split("/")
        
        # Extract the subject ID (subdir) from the path, if available
        sub = extract_subject_from_path(path_parts)
        
        # Extract the file name from the path (the last part)
        assetname = path_parts[-1]
        
        # Parse key-value pairs from the file name (e.g., 'sub-01_task-rest')
        info = parse_asset_filename(assetname)
        
        # If a subject ID was found, add it to the metadata dictionary
        if sub:
            info["subdir"] = sub
        
        # Add the full path to the metadata dictionary
        info["path"] = asset.path
        
        # Extract modality information (e.g., 'bold', 'T1w') from the file name
        modality = extract_modality_from_filename(assetname, asset.path)
        if modality:
            info["modality"] = modality
        
        # Extract the file extension (e.g., 'nii', 'bvec') and add it to the dictionary
        ext = ".".join(assetname.split(".")[1:])
        info["extension"] = ext
        
        # Add the asset's modified date to the metadata dictionary
        info["modified"] = asset.modified
        
        # Append the metadata dictionary for this asset to the list
        asset_info.append(info)
    
    # Convert the list of asset metadata into a pandas DataFrame
    df = pd.DataFrame(asset_info)
    
    # Return both the DataFrame and the original list of assets
    return df, assets



######################## Sections: 2. Generating Modality X Subject Plot
#                                                       &
#                                                     6. Generating Stain X Sample Interactive Plots ########################


def generate_plot(data, title, save_path, interactive=True):
    """
    Generate a Bokeh plot for visualizing subject-modality or sample-stain relationships.

    Args:
    data (pandas.DataFrame): DataFrame containing 'sample', 'stain', and optionally 'url'.
        - 'sample' refers to the x-axis values (e.g., subjects).
        - 'stain' refers to the y-axis values (e.g., modalities).
        - 'url' (optional) is used for interactive plots where clicking on a rectangle opens a URL.
    title (str): Title of the plot, which appears at the top.
    save_path (str): The path to save the generated plot as an HTML file.
    interactive (bool): If True, enables interactive features (e.g., clicking to open URLs and hover tooltips). 
                        If False, generates a non-interactive plot.

    Returns:
    None: The plot is displayed in the browser and saved to the provided `save_path`.
    """
    
    # Create a Bokeh ColumnDataSource from the given DataFrame.
    # ColumnDataSource is the Bokeh format for binding data to plots.
    source = ColumnDataSource(data)

    # Extract unique values for 'sample' (x-axis) and 'stain' (y-axis) from the DataFrame.
    # These unique values are used to define the range of x and y axes.
    x_range = list(data['sample'].unique())
    y_range = list(data['stain'].unique())

    # Determine the number of unique stains (or modalities) to apply distinct colors.
    num_stains = len(y_range)
    
    # Use Category20 palette for up to 20 unique values; otherwise, cycle through Category10 palette.
    palette = Category20[num_stains] if num_stains <= 20 else Category10[num_stains % 10]

    # Create the Bokeh figure object. This is where the plot settings are defined.
    p = figure(
        title=title,  # Title of the plot
        x_range=x_range,  # Set the x-axis range (samples)
        y_range=y_range,  # Set the y-axis range (stains/modalities)
        tools="tap" if interactive else "save",  # Use 'tap' tool only if interactive, otherwise just 'save' tool.
        width=1200,   # Width of the plot, adjusted to display more samples comfortably
        height=600,   # Height of the plot, adjusted to display multiple stains/modalities
        toolbar_location="right"  # Place toolbar (e.g., save button) on the right side for better layout
    )

    # Add rectangles to represent each sample-stain (subject-modality) combination.
    # Rectangles represent the cells in the matrix (e.g., a specific subject with a specific modality).
    p.rect(
        x="sample",  # Set the x-axis to 'sample' values (e.g., subjects)
        y="stain",   # Set the y-axis to 'stain' values (e.g., modalities)
        width=0.9,   # Set the width of each rectangle (close to 1 to fill the space, but with slight spacing)
        height=0.9,  # Set the height of each rectangle
        source=source,  # Provide the data source that contains the x, y values and possibly URLs
        fill_color=factor_cmap('stain', palette=palette, factors=y_range),  # Assign colors based on 'stain'
        line_color=None,  # Remove borders for a cleaner look
    )

    # Add interactive behavior (only if the 'interactive' flag is True)
    if interactive:
        # JavaScript callback that executes when a rectangle is clicked.
        # Opens the URL associated with the clicked rectangle.
        url_callback = CustomJS(args=dict(source=source), code="""
            // Get the index of the clicked rectangle
            const selected = source.selected.indices[0];  
            
            // Retrieve the URL for the selected rectangle
            const url = source.data.url[selected];  

            // If a URL exists, open it in a new tab. Otherwise, alert the user that no URL is available.
            if (url) {
                window.open(url);  // Open the URL in a new window/tab
            } else {
                alert('No URL found for this selection.');
            }
        """)

        # Attach the URL opening functionality to the TapTool, which responds to clicks on rectangles.
        taptool = p.select(type=TapTool)
        taptool.callback = url_callback

    # Rotate the x-axis labels slightly to prevent overlap and ensure readability.
    p.xaxis.major_label_orientation = 1.2  # Rotate the x-axis labels for better readability
    p.xaxis.major_label_text_font_size = "10pt"  # Set font size for x-axis labels
    p.yaxis.major_label_text_font_size = "10pt"  # Set font size for y-axis labels

    # Add hover functionality to display additional information when hovering over rectangles.
    # This is only enabled if 'interactive' is True.
    if interactive:
        # The HoverTool displays tooltips when hovering over a rectangle, showing the sample, stain, and URL.
        hover_tool = HoverTool(
            tooltips=[("Sample", "@sample"), ("Stain", "@stain"), ("URL", "@url")],
            attachment="above"  # Position the tooltip above the hovered rectangle
        )
        p.add_tools(hover_tool)  # Add the hover tool to the plot

    # Define the output file where the plot will be saved (HTML format).
    output_file(save_path)




######################## Section: 5. Generating the Neuroglancer URL ########################


def get_ng_url(sub, sample, stain, modality, url):
    """
    Generate a Neuroglancer URL with the given parameters to visualize the data.

    Parameters:
    sub (str): Subject identifier.
    sample (str): Sample identifier.
    stain (str): Stain identifier.
    modality (str): Modality identifier.
    url (str): The URL to the Zarr dataset.

    Returns:
    str: A complete Neuroglancer URL to visualize the dataset.
    """

    # Create the Neuroglancer layer configuration
    layer = {
        "type": "image",  # Define the layer type as 'image'
        "source": f"zarr://{url}",  # Source of the layer, using the Zarr format from the given URL
        "tab": "rendering",  # Specify the tab in Neuroglancer (rendering tab)
        "shaderControls": {"normalized": {"range": [0,1250]}},  # Shader controls for brightness/contrast range
        "name": f"{sub}-{sample}-{stain}-{modality}"  # Create a descriptive name for the layer based on input parameters
    }

    # Neuroglancer base URL for constructing the final visualization link
    base_url = "https://neuroglancer-demo.appspot.com/#!"

    # Configuration for Neuroglancer, including dimensions, layers, and layout
    config = {
        "dimensions": {
            "z": [0.0000036, "m"],  # Z dimension with a resolution scale in meters
            "y": [0.0000036, "m"],  # Y dimension with a resolution scale in meters
            "x": [0.0000036, "m"]   # X dimension with a resolution scale in meters
        },
        "layers": [layer],  # Add the layer configuration defined above
        "layout": 'yz',  # Layout of the visualization (in this case, along the yz-plane)
    }

    # Convert the configuration to a JSON string and encode it as part of the URL
    ng_url = base_url + quote(json.dumps(config))

    # Return the full Neuroglancer URL
    return ng_url



######################## Main function 


def main():
    
    ##################### Variables

    # Creating esstential directories
    # directory to save pickle objects
    object_dict = "./objs"
    # create directory
    try:
        os.mkdir(object_dict)
    except:
        print(f"Note: {object_dict} to store pickle objects already exist.")

    # plots directory
    plots_dict = "./plots"
    # Create the directory 
    try:
        os.mkdir(plots_dict)
    except:
        print(f"Note: {plots_dict} to store plots objects already exist.")

    # Dandi dataset ID
    dandi_set = "000026"

    # API call
    api = "https://api.dandiarchive.org/api"
    dandi_api = DandiAPIClient(api)

    # Getting the dataset from the dandi server
    dandi_dataset = dandi_api.get_dandiset(dandi_set)

    # Saving the dandi_dataset object
    with open(f'{object_dict}/dandiset.pkl', 'wb') as file:
        pickle.dump(dandi_dataset, file)


    ##################### 1. Data Gathering

    print("Gathering Data.")

    # Load the dandiset object from the saved file
    with open(f'{object_dict}/dandiset.pkl', 'rb') as file:
        dandi_dataset = pickle.load(file)

    # data gathering
    df, assets = assets_to_df(dandi_dataset)
    # Saving the gathered data
    with open(f'{object_dict}/rawData.pkl', 'wb') as file:
        pickle.dump((df, assets), file)

    print("\t\t1/7 Done!")


    ##################### 2. Generating Modality X Subject Plot

    print("Generating Modality X Subject Plot.")

    # Load the gathered data from the saved file
    with open(f'{object_dict}/rawData.pkl', 'rb') as file:
        df, assets = pickle.load(file)

    # Specify the modalities 
    selected_modalities = ["STER", "SPIM", "OCT"]

    # only taking the sub and modality data copy
    df_modXsub = df[['sub', 'modality']].copy()
    df_modXsub = df_modXsub.dropna()


    # selecting data  with specific modaility
    df_modXsub = df_modXsub[df_modXsub['modality'].isin(selected_modalities)].copy()
     # Rename for consistency in the function for generate_plot()
    df_modXsub.rename(columns={"sub": "sample", "modality": "stain"}, inplace=True) 

    # sort the data on the bases of sample and each sample on the bases of stain
    df_modXsub = df_modXsub.sort_values(by=['sample', 'stain'], ascending=[True, True])


    # plot title
    modXsub_plt_title = "Modality x Subject"
    # path to save the modality subject plot
    modXsub_plt_path = f"{plots_dict}/modality_subject.html"
    # Generate a non-interactive plot
    generate_plot(df_modXsub, title=modXsub_plt_title, save_path=modXsub_plt_path, interactive=False)

    print("\t\t2/7 Done!")


    ##################### 3. Refining to the data with modality: SPIM and extension: ome.zarr

    print("Refining to SPIM Data with ome.zarr Extensions.")

    # Refining the data
    df_refined = df[(df['modality'].isin(["SPIM"])) & (df['extension']=='ome.zarr')]
    # Only taking the sub, sample, stain and modality columns
    df_refined = df_refined[['sub', 'sample', 'stain', 'modality']]

    print("\t\t3/7 Done!")


    ##################### 4. Getting the AmazonAWS URL

    print("Getting the AmazonAWS URL")

    # create a copy
    df_aaws = df_refined.copy()

    # get the url for each row based on the index from the assests dataset
    df_aaws['url'] = [assets[i].get_content_url(regex='s3') for i in df_aaws.index]

    # Saving the final dataset
    with open(f'{object_dict}/df_aaws.pkl', 'wb') as file:
        pickle.dump(df_aaws, file)

    print("\t\t4/7 Done!")

    
    ##################### 5. Generating the Neuroglancer URL

    print("Generating the Neuroglancer URL")

    # Load the df_aaws data from the saved file
    with open(f'{object_dict}/df_aaws.pkl', 'rb') as file:
        df_aaws = pickle.load(file)


    # sort based on sub 
    df_final = df_aaws.sort_values(by='sub')


    # generate the url
    df_final['url'] = df_final.apply(lambda row: get_ng_url(row['sub'], row['sample'], row['stain'], row['modality'], row['url']), axis=1)

    # Saving the dandi_dataset object
    with open(f'{object_dict}/df_final.pkl', 'wb') as file:
        pickle.dump(df_final, file)

    print("\t\t5/7 Done!")

    
    ##################### 6. Generating Stain X Sample Interactive Plots

    print("Generating Stain X Sample Interactive Plots")

    # Load the df_final data from the saved file
    with open(f'{object_dict}/df_final.pkl', 'rb') as file:
        df_final = pickle.load(file)

    # getting all subs
    subs = df_final['sub'].unique()

    # contains the location info of the genrated plots
    plots_loc = dict()
    # adding the modaility x strin plot path
    plots_loc['Modailty X Subject'] = modXsub_plt_path

    # for every sub
    for sub_name in subs:
        # get all the rows of that particular sub, for example I48
        df_sub = df_final[(df_final['sub'] == sub_name)]

        # sort the data on the bases of sample and each sample on the 
        # bases of stain
        df_sub = df_sub.sort_values(by = ['sample', 'stain'], ascending=[True, True])

        # create the title for the plot
        title = f"{sub_name} - Stain x Sample"
        # path where to save the plot
        save_path = f"{plots_dict}/{sub_name}.html"
        # save the path info
        plots_loc[sub_name] = save_path

        # generate and save the interactive plot
        generate_plot(df_sub, title, save_path, True)

    print("\t\t6/7 Done!")


    ##################### 7. Create the Main HTML Page

    print("Create the HTML Page")

    # directory where the template is located
    template_dir = os.path.dirname(os.path.abspath("__file__"))
    # Load the template environment
    env = Environment(loader=FileSystemLoader(template_dir))
    # Load the template
    template = env.get_template('temp/template.html')

    # Render the template with the plots_loc data
    rendered_html = template.render(subs=plots_loc)

    # Save the rendered HTML to a new file
    with open('DANDI_interactive_plot_selector.html', 'w') as output_file:
        output_file.write(rendered_html)

    print("\t\t7/7 Done!\n\n")

    print("HTML file generated as 'DANDI_interactive_plot_selector.html'")



if __name__ == "__main__":
    main()
