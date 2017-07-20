#!/usr/bin/env python3

import os
import cv2
import yaml
import random
import argparse
import numpy as np

from CellDetector import CellDetector
from NeuralNetwork import NeuralNetwork
from Sample import Sample


def main(args):
    """
    :param args:
    :return:
    """
    ds = DiagnosisSystem(args.config)
    while True:
        option = input("""What would you like to do?
    1. train
    2. load model
    3. evaluate
    4. diagnose
    5. quit\n""")
        if option == "train" or option == "1":
            ds.train()
        elif option == "load model" or option == "2":
            ds.load_model()
        elif option == "evaluate" or option == "3":
            ds.evaluate()
        elif option == "diagnose" or option == "4":
            ds.diagnose()
        elif option == "quit" or option == "5":
            break
        else:
            print("Invalid selection.")


class DiagnosisSystem(object):

    def __init__(self, yaml_path):
        """
        :param yaml_path:
        """
        self._yaml_path = "../config/" + yaml_path
        self._neural_network = NeuralNetwork(yaml_path)
        self._cell_detector = CellDetector(yaml_path)
        self._image_shape = None
        self._train_config = None
        self._evaluate_config = None
        self._diagnose_config = None
        self.update_config()

    def update_config(self):
        """
        :return:
        """
        try:
            self._train_config = self._get_yaml_dict(self._yaml_path)["train"]
            self._evaluate_config = self._get_yaml_dict(self._yaml_path)["evaluate"]
            self._diagnose_config = self._get_yaml_dict(self._yaml_path)["diagnose"]
            image_config = self._get_yaml_dict(self._yaml_path)["images"]
            self._image_shape = (image_config["width"],
                                 image_config["height"],
                                 image_config["depth"])
        except KeyError:
            print("Warning: some entries were missing from the configuration file.")

    def train(self):
        """
        :return:
        """
        self.update_config()
        data = []
        for label in self._train_config["labels"]:
            directories = self._train_config["labels"][label]["directories"]    # Get directories from config
            if directories is not None:                                         # If directories are given
                data += self._get_cell_data(directories, label)                 # Make a list of images and labels
        if data:
            random.shuffle(data)                                                # Shuffle the data
            x, y = self._list_to_arrays(data, self._image_shape)                # Put the data into numpy arrays
            x = self._normalise(x)
            cont = self._check_balance(y)                                       # Check that data is balanced
            if cont:
                self._neural_network.train(x, y)

    def load_model(self):
        """
        :return:
        """
        self._neural_network.load_model()

    def save_model(self):
        """
        :return:
        """
        self._neural_network.save_model()

    def draw_model(self):
        """
        :return:
        """
        self._neural_network.draw_model()

    def save_history(self):
        """
        :return:
        """
        self._neural_network.save_history()

    def plot_history(self):
        """
        :return:
        """
        self._neural_network.plot_history()

    def evaluate(self):
        """
        :return:
        """
        self.update_config()
        num_classes = len(self._evaluate_config["labels"])                              # Get number of classes
        for label in self._evaluate_config["labels"]:                                   # Evaluate each label separately
            directories = self._evaluate_config["labels"][label]["directories"]         # Get directories
            if directories is not None:                                                 # If directories given
                data = self._get_cell_data(directories, label)                          # Get imgs from list of dirs
                if data:                                                                # If there are images
                    x, y = self._list_to_arrays(data, self._image_shape)
                    x = self._normalise(x)
                    self._neural_network.evaluate(x, y, num_classes=num_classes)

    def diagnose(self):
        """
        :return:
        """
        self.update_config()
        if self._neural_network.is_ready():
            directories = self._diagnose_config["directories"]
            samples = self._load_samples(directories)
            for sample in samples:                                                          # For each sample
                print("Diagnosing sample " + sample.get_id() + "...")
                for image in sample.get_images():                                           # Gor each image
                    image.add_cells(self._cell_detector.run(image))                         # Add cells to image
                    x = self._cells_to_arrays(image.get_cells(complete=True),
                                              self._image_shape)                            # Np array of images
                    x = self._normalise(x)                                                  # Normalise the array
                    predictions = self._neural_network.predict(x)                           # Get array predictions
                    for i, cell in enumerate(image.get_cells(complete=True)):
                        cell.set_prediction(np.argmax(predictions[i]))                      # Set its predicted status
                        cell.set_confidence(np.max(predictions[i]))                         # Store the confidence value
                    img = image.draw_cells()                                                # Draw each cell
                    destination = "../" + self._diagnose_config["destination"] + \
                                  "/" + self._neural_network.get_name() + \
                                  "/" + sample.get_id() + \
                                  "/" + image.get_name()                                    # Results destination
                    self._save_image(img, image.get_name() + "." + image.get_type(),
                                     destination)                                           # Save the whole
                    self._save_cells(image.get_cells(), destination)                        # Save each cell image
                    self._log_cells(image.get_cells(), destination)                         # Write a log file for image
                print("Sample id: " + sample.get_id())
                print("\tTotal cells: " + str(sample.total_cells()))
                print("\tHealthy cells: " + str(sample.total_cells(0)))
                print("\tInfected cells: " + str(sample.total_cells(1)))
        else:
            print("Warning: classification model is not yet complied.")

    def _load_samples(self, directories):
        """
        :param directories:
        :return:
        """
        print("Loading samples...")
        samples = []
        directories = ["../" + directory for directory in directories]                  # Change initial dir
        if directories is not None:
            for directory in directories:
                if os.path.isdir(directory):
                    image_paths = os.listdir(directory)
                    image_paths = [directory + "/" + path for path in image_paths]
                    image_paths = self._check_images(image_paths)
                    for image_path in image_paths:
                        sample_id = self._get_sample_id(image_path)
                        if sample_id is not None:
                            sample_index = self._get_sample_index(samples, sample_id)
                            if sample_index != -1:
                                samples[sample_index].add_image(image_path)
                            else:
                                sample = Sample(sample_id)
                                sample.add_image(image_path)
                                samples.append(sample)
                    if len(samples) == 1:
                        print("1 sample found.")
                    else:
                        print(str(len(samples)) + " samples found.")
                else:
                    print("Warning: " + directory + " not found.")
        else:
            print("Warning: No directories given.")
        return samples

    def _get_cell_data(self, directories, label):
        """
        :param directories: list of paths to directories containing cells
        :param label: label to describe the cells in the directories
        :return: list of images and labels
        """
        data = []
        small = 0
        directories = ["../" + directory for directory in directories]              # Change initial dir
        for directory in directories:                                               # For each directory
            if os.path.isdir(directory):                                            # If the directory exists
                image_paths = os.listdir(directory)                                 # Get the file names in the dir
                image_paths = [directory + "/" + path for path in image_paths]      # Get the full file path
                image_paths = self._check_images(image_paths)                       # Check the files are images
                for path in image_paths:                                            # For each cell path
                    img = cv2.imread(path)                                          # Get the cell image
                    if img.shape == self._image_shape:                              # If image is the required shape
                        data.append([img, label])                                   # Append image and label to data
                    else:
                        small += 1
            else:
                print("Warning: " + directory + " not found.")
        print("Warning: " + str(small) + " images from label " + str(label) + " were too small.")
        return data

    def _save_cells(self, cells, destination):
        """
        :param cells: list of Cell objects
        :param destination: directory to save the cells in
        """
        for cell in cells:                                                          # For each cell
            if cell.get_prediction() == 0:                                          # If cell prediction is healthy
                folder = "healthy"                                                  # Set folder to healthy
            elif cell.get_prediction() == 1:                                        # If cell prediction is infected
                folder = "falciparum"                                               # Set folder to falciparum
            else:
                folder = "unclassified"                                             # Set folder to unclassified
            directory = destination + "/" + folder                                  # Set destination directory
            self._save_image(cell.get_image(),
                             cell.get_id() + ".jpg",
                             directory)                                             # Save image of cell

    @staticmethod
    def _log_cells(cells, destination):
        """
        :param cells: list of Cell objects
        :param destination: directory in which to save the log
        """
        filename = destination + "/results.csv"                                     # Set name of log file
        file = open(filename, "w")                                                  # Open the log file
        file.write("Sample,Image,Cell,X,Y,Prediction,Confidence,Complete\n")        # Write the column headers
        for i, cell in enumerate(cells):                                            # For each cell
            attributes = [cell.get_sample_id(),                                     # Get the cell attributes
                          cell.get_image_id(),
                          cell.get_nb(),
                          cell.get_position()[0],
                          cell.get_position()[1],
                          cell.get_prediction(),
                          cell.get_confidence(),
                          cell.is_complete()]
            file.write(",".join(list(map(str, attributes))) + "\n")                 # Print attributes, comma separated
        file.close()                                                                # Close file
        print("Log saved to " + filename + ".")                                     # Tell user where to find the log

    @staticmethod
    def _normalise(x):
        """
        :param x: numpy array of images
        :return x: numpy array of normalised images
        """
        x = x.astype("float32")                                                     # Convert to float32
        x /= 255                                                                    # Normalise
        return x

    @staticmethod
    def _check_balance(y):
        """
        :param y: numpy array of labels
        :return: bool to signify if the user wishes to continue
        """
        cont = True                                                                 # Signify to continue
        classes = np.unique(y)                                                      # Find the number of classes
        class_freq = [np.sum(y == label) for label in classes]                      # Get the frequency of each class
        if not all(class_freq[0] == item for item in class_freq):                   # If class freq values are not equal
            print("Warning: unbalanced data, " + str(class_freq) + ".")             # The data set is unbalanced
            while True:
                cont = input("Continue? y/n\n")                                     # Ask user if they want to continue
                if cont == "y":
                    break
                elif cont == "n":
                    cont = False
                    break
        return cont

    @staticmethod
    def _get_sample_index(samples, sample_id):
        """
        :param samples: a list of Sample objects
        :param sample_id: the id of a sample
        :return: index number of the sample in the list
        """
        index = -1                                                                  # -1 if sample id does not exist
        for i, sample in enumerate(samples):                                        # For each sample
            if sample_id == sample.get_id():                                        # If the sample id matches
                index = i                                                           # Note the sample index
                break                                                               # Break
        return index                                                                # Return the sample index

    @staticmethod
    def _list_to_arrays(data, shape):
        """
        :param data: list of lists containing the cell image and its label
        :param shape: tuple to describe the expected image shape
        :return: numpy arrays of images and labels
        """
        y = np.empty((len(data), 1), dtype=np.uint8)                                # Init labels array
        x = np.zeros((len(data), shape[0], shape[1], shape[2]), dtype=np.uint8)     # Init data array
        for i, (image, label) in enumerate(data):                                   # Put data into numpy arrays
            height, width, depth = image.shape                                      # Get the image shape
            x[i, 0:height, 0:width, 0:depth] = image                                # x contains images
            y[i] = label                                                            # y contains labels
        return x, y

    @staticmethod
    def _cells_to_arrays(cells, shape):
        """
        :param cells: list of cell objects
        :param shape: tuple to describe the expected shape of the images
        :return: numpy array of cell images
        """
        x = np.empty((len(cells), shape[0], shape[1], shape[2]), dtype=np.uint8)    # Init array to store images
        for i, cell in enumerate(cells):                                            # For each cell
            cell_image = cell.get_image(dx=shape[0], dy=shape[1])                   # Get the cell image
            width, height, depth = cell_image.shape                                 # Get image dimensions
            x[i, 0:width, 0:height, 0:depth] = cell_image                           # Add cell to the array
        return x

    @staticmethod
    def _get_sample_id(image_path):
        """
        :param image_path:
        :return:
        """
        try:
            sample_id = image_path.split("/")[-1].split("_")[-2]
        except IndexError:
            print("Warning: no image name found in " + image_path + ".")
            sample_id = None
        return sample_id

    @staticmethod
    def _check_images(image_paths):
        """
        Checks that file paths are valid image and removes non jpg/png files
        :param image_paths: List of paths to images
        :return: list of paths to images
        """
        images = []                                                                 # List to store image paths
        for path in image_paths:                                                    # For each image_path
            if os.path.isfile(path):                                                # Check the given path is a file
                ext = path.split(".")[-1]                                           # Get the file extension
                if ext == "jpg" or "png":                                           # If the image is a png or jpg
                    images.append(path)                                             # Append image path to image_paths
        return images

    @staticmethod
    def _save_image(image, image_name, destination):
        """
        Saves the image in a given directory
        Creates the directory if it does not already exist
        :param image: image to save
        :param image_name: name to save image as
        :param destination: directory to save image in
        """
        directories = destination.split("/")                                        # Get list of directories
        path = ""                                                                   # Init path string
        for directory in directories:                                               # For each directory
            path += directory + "/"                                                 # Add it to the path
            if not os.path.isdir(path):                                             # If it does not yet exist
                os.mkdir(path)                                                      # Make it
        cv2.imwrite(path + "/" + image_name, image)                                 # Save image to path

    @staticmethod
    def _get_yaml_dict(yaml_path):
        """
        :param yaml_path: path to a yaml file
        :return: dictionary containing the contents of the yaml fle
        """
        yaml_dict = {}                                                              # Initialise yaml_dict
        if os.path.isfile(yaml_path):                                               # If the file exists
            with open(yaml_path) as file:                                           # Open the file
                yaml_dict = yaml.load(file)                                         # Load the file
        else:
            print("Warning: " + yaml_path + " not found.")
        return yaml_dict

if __name__ == "__main__":
    parser = argparse.ArgumentParser()                                              # Initialise the parser
    parser.add_argument("--config", default="config.yaml")                          # Add an argument for config
    arguments = parser.parse_args()                                                 # Get the arguments
    main(arguments)                                                                 # Run the diagnosis system

