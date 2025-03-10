import torch
import numpy as np
import matplotlib.pyplot as plt
from functools import reduce
from typing import Optional

import torchvision
from torchvision import datasets, transforms

from visualization.augmentations.trivial_augment import CustomTrivialAugmentWide
from visualization.augmentations.random_crop import RandomCrop
from visualization.augmentations.random_choice import RandomChoiceTransforms
from visualization.augmentations.random_erasing import RandomErasing


import random

class AugmentedDataset(torch.utils.data.Dataset):
    """Dataset wrapper to perform augmentations and allow robust loss functions.

    Attributes:
        dataset (torch.utils.data.Dataset): The base dataset to augment.
        transforms_preprocess (transforms.Compose): Transformations for preprocessing.
        transforms_augmentation (transforms.Compose): Transformations for augmentation.
        transforms_generated (transforms.Compose): Transformations for generated samples.
        robust_samples (int): Number of robust samples to include.
    """

    def __init__(
        self,
        dataset,
        transforms_preprocess,
        transforms_augmentation,
        transforms_generated=None,
        robust_samples=0,
    ):
        if dataset is not None:
            self.dataset = dataset

        self.preprocess = transforms_preprocess
        self.transforms_augmentation = transforms_augmentation
        self.transforms_generated = (
            transforms_generated if transforms_generated else transforms_augmentation
        )
        self.robust_samples = robust_samples
        self.original_length = getattr(dataset, "original_length", None)
        self.generated_length = getattr(dataset, "generated_length", None)

    def get_confidence(self, confidences: Optional[tuple]) -> Optional[float]:
        """Combines multiple confidence values into a single value.

        Args:
            confidences (Optional[tuple]): A tuple of confidence values.

        Returns:
            Optional[float]: The combined confidence value.
        """
        combined_confidence = reduce(lambda x, y: x * y, confidences)
        # print(f"Confidences: {confidences}\tCombined Confidence: {combined_confidence}\n")
        return combined_confidence

    def __getitem__(self, i: Optional[int]) -> Optional[tuple]:
        """Retrieves an item from the dataset and applies augmentations.

        Args:
            i (Optional[int]): Index of the item to retrieve.

        Returns:
            Optional[tuple]: The augmented image, the label, and the combined confidence value.
        """
        x, y = self.dataset[i]
        confidences = None
        augmentation_magnitude = None
        combined_confidence = torch.tensor(1.0, dtype=torch.float32)
        original = True  # for now "original" is set to True rather than returning from base_dataset

        augment = (
            self.transforms_augmentation
            if original == True
            else self.transforms_generated
        )

        if isinstance(x, tuple):
            raise ValueError("Tuple not supported")
        augment_x = augment(x)

        if isinstance(augment_x, tuple):
            confidences = augment_x[1]
            augment_x = augment_x[0]
            if isinstance(confidences, tuple):
                combined_confidence = self.get_confidence(confidences)
            elif isinstance(confidences, list):
                combined_confidence = confidences[1]
                augmentation_magnitude = confidences[0]
            else:
                combined_confidence = confidences

        if not isinstance(augment_x, torch.Tensor):
            augment_x = self.preprocess(augment_x)

        if self.robust_samples == 0:
            if augmentation_magnitude is not None:
                return augment_x, y, [augmentation_magnitude, combined_confidence]
            return augment_x, y, combined_confidence

    def __len__(self):
        return len(self.dataset)


def create_transforms(
    random_erasing: bool = False,
    random_cropping: bool = False,
    aggressive_augmentation: bool = False,
    custom: bool = False,
    augmentation_name: str = None,
    augmentation_severity: int = 0,
    augmentation_sign: bool = False,
    dataset_name: str = "CIFAR10",
    seed: Optional[int] = None,
    individual_analysis: Optional[bool] = False,
    mapping_approach: Optional[str] = "exact_model_accuracy",
) -> Optional[tuple]:
    """Creates preprocessing and augmentation transformations.

    Args:
        random_erasing (bool, optional): Flag to include random erasing in augmentations. Defaults to False.
        random_cropping (bool, optional): Flag to include random cropping in augmentations. Defaults to False.
        aggressive_augmentation (bool, optional): Flag to include aggressive augmentations. Defaults to False.
        custom (bool, optional): Flag to use custom trivial augmentations. Defaults to False.
        augmentation_name (str, optional): Name of the custom augmentation (if applicable).
        augmentation_severity (int, optional): Severity level for custom augmentations. Defaults to 0.
        augmentation_sign (bool, optional): Flag to determine if augmentation should be signed. Defaults to False.
        dataset_name (str, optional): Name of the dataset. Defaults to "CIFAR10".
        seed (int, optional): Random seed for reproducibility.
        individual_analysis (bool, optional): Whether to perform individual analysis of augmentations.
        mapping_approach (str, optional): Approach for mapping confidence. Defaults to "exact_model_accuracy".

    Returns:
        Optional[tuple]: The preprocessing and augmentation transformations.
    """
    t = [transforms.ToTensor()]
    augmentations = [
        transforms.RandomHorizontalFlip(),
        transforms.RandomCrop(32, padding=4),       # For Tiny-ImageNet: 64 x 64; For CIFAR: 32 x 32
    ]

    print(f"Calculating confidence with the mapping approach: {mapping_approach}\n")

    """Sequential Augmentations"""
    if aggressive_augmentation:
        if custom:
            augmentations.append(
                CustomTrivialAugmentWide(
                    custom=custom,
                    augmentation_name=augmentation_name,
                    severity=augmentation_severity,
                    get_signed=augmentation_sign,
                    dataset_name=dataset_name,
                    individual_analysis=individual_analysis,
                    mapping_approach=mapping_approach,
                ))
        else:
            augmentations.extend([transforms.TrivialAugmentWide()])
    if random_cropping:
        if aggressive_augmentation:
            augmentations.pop(-2)       # -1, -2(if sequential)
        else:
            augmentations.pop(-1)
        augmentations.append(RandomCrop(dataset_name=dataset_name, custom=custom, seed=seed))
    
    if random_erasing:
        augmentations.append(transforms.TrivialAugmentWide())
        augmentations.append(RandomErasing(p=0.3, scale=(0.02, 0.33), ratio=(0.3, 3.3), value='random', custom=custom, dataset_name=dataset_name))
    """Sequential Augmentations"""
        

    """Parallel Augmentations"""
    # custom_trivial_augment = CustomTrivialAugmentWide(
    #     custom=custom,
    #     augmentation_name=augmentation_name,
    #     severity=augmentation_severity,
    #     get_signed=augmentation_sign,
    #     dataset_name=dataset_name,
    # )
    # random_crop_augment = RandomCrop(dataset_name=dataset_name, custom=custom)

    # if aggressive_augmentation:
    #     augmentations.append(
    #         RandomChoiceTransforms(
    #             [transforms.TrivialAugmentWide(), random_crop_augment], [0.85, 0.15]
    #         )
    #     )
    # if random_cropping:
    #     augmentations.pop(-2)        # -1, -2(if sequential)
    """Parallel Augmentations"""

    transforms_preprocess = transforms.Compose(t)
    transforms_augmentation = transforms.Compose(augmentations)

    return transforms_preprocess, transforms_augmentation


def load_data(
    transforms_preprocess,
    transforms_augmentation=None,
    dataset_split: Optional[int] = "full",
    dataset_name: Optional[str] = "CIFAR10",
) -> Optional[tuple]:
    """Loads and prepares a dataset (CIFAR-10, CIFAR-100, or Tiny-ImageNet) with specified transformations.

    Args:
        transforms_preprocess (transforms.Compose): Preprocessing transformations.
        transforms_augmentation (transforms.Compose, optional): Augmentation transformations.
        dataset_split (int or str, optional): Number of samples to retain for faster testing. 
            If "full", the entire dataset is used.
        dataset_name (str, optional): Name of the dataset to load. Supports "CIFAR10", "CIFAR100", and "Tiny-ImageNet".

    Returns:
        Optional[tuple]: The processed training and testing datasets.
    """

    if dataset_name == "CIFAR10":
        # CIFAR-10
        base_trainset = datasets.CIFAR10(root="./data/train", train=True, download=True)
        base_testset = datasets.CIFAR10(root="./data/test", train=False, download=True)
    elif dataset_name == "CIFAR100":
        # CIFAR-100
        base_trainset = datasets.CIFAR100(root="./data/train", train=True, download=True)
        base_testset = datasets.CIFAR100(root="./data/test", train=False, download=True)
    elif dataset_name == "Tiny-ImageNet":
        base_trainset = datasets.ImageFolder(root="./data/tiny-imagenet-200/new_train")
        base_testset = datasets.ImageFolder(root="./data/tiny-imagenet-200/new_test")
    else:
        raise ValueError(f"Dataset {dataset_name} not supported")

    """MODIFICATION: Truncate the dataset to a smaller size for faster testing"""
    if dataset_split != "full":
        truncated_trainset = torch.utils.data.Subset(
            base_trainset, range(dataset_split)
        )
        truncated_testset = torch.utils.data.Subset(base_testset, range(dataset_split))
    else:
        truncated_trainset = base_trainset
        truncated_testset = base_testset
    """MODIFICATION: Truncate the dataset to a smaller size for faster testing"""

    if transforms_augmentation is not None:
        trainset = AugmentedDataset(
            dataset=truncated_trainset,
            transforms_preprocess=transforms_preprocess,
            transforms_augmentation=transforms_augmentation,
        )

        testset = AugmentedDataset(
            dataset=truncated_testset,
            transforms_preprocess=transforms_preprocess,
            transforms_augmentation=transforms_augmentation,
        )
    elif base_trainset.__class__.__name__ == "CIFAR10":
        trainset = datasets.CIFAR10(
            root="./data/train",
            train=True,
            download=True,
            transform=transforms_preprocess,
        )
        testset = datasets.CIFAR10(
            root="./data/test",
            train=False,
            transform=transforms_preprocess,
            download=True,
        )
    elif base_trainset.__class__.__name__ == "CIFAR100":
        trainset = datasets.CIFAR100(
            root="./data/train",
            train=True,
            download=True,
            transform=transforms_preprocess,
        )
        testset = datasets.CIFAR100(
            root="./data/test",
            train=False,
            transform=transforms_preprocess,
            download=True,
        )

    return trainset, testset


def display_image_grid(images, labels, confidences, batch_size, classes):
    """
    Displays a 5x5 grid of images with labels and confidence scores.

    Args:
        images (torch.Tensor): Batch of images.
        labels (torch.Tensor): Corresponding labels for the images.
        confidences (torch.Tensor): Corresponding confidence scores for the images.
        batch_size (int): Number of images to display in the grid (should be 25 for a 5x5 grid).
        classes (list): List of class names for labeling.
    """
    # Limit batch_size to 25 for a 5x5 grid
    batch_size = min(batch_size, 25)
    
    if isinstance(confidences, list):
        confidences = confidences[1]

    # Convert images to a grid, with 5 images per row
    grid_img = torchvision.utils.make_grid(images[:batch_size], nrow=5)

    # Convert from tensor to numpy for display
    npimg = grid_img.numpy()

    # Plot the grid with appropriate figure size (for 5x5 grid)
    plt.figure(figsize=(10, 10))
    plt.imshow(np.transpose(npimg, (1, 2, 0)))
    plt.axis("off")

    # Add titles for each image (labels and confidence scores)
    for i in range(batch_size):
        ax = plt.subplot(5, 5, i + 1)  # Adjust to a 5x5 grid
        ax.imshow(np.transpose(images[i].numpy(), (1, 2, 0)))
        ax.set_title(
            f"{labels[i].item()} ({classes[labels[i].item()]})\nConf: {confidences[i]:.2f}",
            fontsize=8
        )
        ax.axis("off")

    plt.show()

def seed_worker():
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    torch.seed(worker_seed)


if __name__ == "__main__":

    # Set the batch size for the data loader
    batch_size = 5000
    DATASET_NAME = "CIFAR10"

    # Set the random seed for reproducibility
    g = torch.Generator()
    g.manual_seed(1)

    # For individual augmentation analysis
    augmentation_type = "Brightness"
    augmentation_severity = 15
    augmentation_sign = True

    # Mapping approach for confidence calculation
    """
    Mapping Approaches:
    1. exact_model_accuracy
    2. smoothened_hvs
    3. fixed_params
    4. exact_hvs
    5. ssim_metric
    6. uiq_metric
    7. ncc_metric
    8. scc_metric
    9. sift_metric
    """
    # Create the transformations for preprocessing and augmentation
    transforms_preprocess, transforms_augmentation = create_transforms(random_erasing=False,
                                                                       random_cropping=False, 
                                                                       aggressive_augmentation=True, 
                                                                       custom=True, 
                                                                       augmentation_name=augmentation_type, 
                                                                       augmentation_severity=augmentation_severity, 
                                                                       augmentation_sign=augmentation_sign, 
                                                                       dataset_name=DATASET_NAME,
                                                                       mapping_approach="fixed_params")
    
    print(transforms_augmentation)

    # Load the CIFAR-10 dataset with the specified transformations
    trainset, testset = load_data(transforms_preprocess=transforms_preprocess, 
                                  transforms_augmentation=transforms_augmentation, 
                                  dataset_name=DATASET_NAME)

    # Create a data loader for the training set
    trainloader = torch.utils.data.DataLoader(trainset, 
                                              batch_size=batch_size, 
                                              shuffle=False, 
                                              worker_init_fn=seed_worker, 
                                              generator=g)

    # Display a grid of images with labels and confidence scores
    classes = trainset.dataset.classes
    images, labels, confidences = next(iter(trainloader))
    # display_image_grid(images, labels, confidences, batch_size=batch_size, classes=classes)
    print(f"Confidence: {confidences}")

